import json
import logging
import re
from celery import shared_task
from django.conf import settings
import google.generativeai as genai

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status, get_plan_tier

logger = logging.getLogger(__name__)

_gemini_configured = False


@shared_task(bind=True, max_retries=3)
def analyze_semantic_task(self, video_id: str) -> dict:
    video = None
    try:
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "analyzing"
        video.current_step = "analyzing"
        video.save()
        update_job_status(str(video.video_id), "analyzing", progress=45, current_step="analyzing")

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        formatted_text = _format_transcript_with_timestamps(transcript.segments)
        language = transcript.language

        min_d, max_d = _get_duration_bounds(video_id=str(video.video_id))
        analysis_result = _analyze_with_gemini(formatted_text, language, min_duration=min_d, max_duration=max_d)

        if "candidates" in analysis_result:
            for c in analysis_result["candidates"]:
                c["start_time"] = _clean_number(c.get("start_time", 0))
                c["end_time"] = _clean_number(c.get("end_time", 0))
                c["engagement_score"] = _clean_number(c.get("engagement_score", 0))

        transcript.analysis_data = analysis_result
        transcript.save()

        video.last_successful_step = "analyzing"
        video.status = "embedding"
        video.current_step = "embedding"
        video.save()
        
        update_job_status(str(video.video_id), "embedding", progress=50, current_step="embedding")

        from .embed_classify_task import embed_classify_task
        embed_classify_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.classify.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "candidates_found": len(analysis_result.get("candidates", [])),
        }

    except Video.DoesNotExist:
        logger.error(f"Vídeo não encontrado: {video_id}")
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro na análise semântica: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.retry_count += 1
            video.save()

            msg = str(e)
            non_retryable = (
                "Could not extract valid JSON" in msg
                or "Empty response text" in msg
                or "Response text is not a string" in msg
            )

            if not non_retryable and self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _configure_gemini():
    global _gemini_configured
    if _gemini_configured:
        return
    
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise Exception("GEMINI_API_KEY não configurada")
    
    genai.configure(api_key=api_key)
    _gemini_configured = True


def _format_transcript_with_timestamps(segments: list) -> str:
    if not segments:
        return ""
    
    buffer = []
    for seg in segments:
        start = seg.get('start', 0)
        end = seg.get('end', 0)
        text = seg.get('text', '').strip()
        buffer.append(f"[{start:.1f}-{end:.1f}] {text}")
    
    return "\n".join(buffer)


def _clean_number(num):
    """Converte 10.0 para 10 (int), mas mantém 5.8 (float)."""
    try:
        f_num = float(num)
        if f_num.is_integer():
            return int(f_num)
        return f_num
    except:
        return num


def _analyze_with_gemini(formatted_text: str, language: str, min_duration: int, max_duration: int) -> dict:
    _configure_gemini()
    
    response_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "start_time": {"type": "number"},
                        "end_time": {"type": "number"},
                        "engagement_score": {"type": "number"},
                        "hook_title": {"type": "string"},
                        "tone": {"type": "string"},
                    },
                    "required": ["text", "start_time", "end_time", "engagement_score", "hook_title", "tone"]
                }
            },
            "overall_tone": {"type": "string"},
            "key_topics": {
                "type": "array",
                "items": {"type": "string"}
            },
        },
        "required": ["title", "description", "candidates", "overall_tone", "key_topics"]
    }
    
    base_instructions = f"""
    Você é um editor de vídeo de classe mundial e estrategista de conteúdo viral.
    Analise a transcrição fornecida (que contém timestamps no formato [início-fim]).
    Sua missão é identificar os segmentos com maior potencial viral para Shorts, Reels e TikTok.

    DIRETRIZES CRÍTICAS DE ANÁLISE:
    1. Timestamps Exatos: Use ESTRITAMENTE os timestamps fornecidos no texto (`start_time` e `end_time`). NUNCA alucine ou invente tempos que não existem na transcrição.
    2. Duração: Os clips devem ter entre {min_duration} e {max_duration} segundos.
    3. Contexto: Selecione apenas segmentos que tenham início, meio e fim lógicos (que façam sentido sozinhos).
    3.1. Autossuficiência: Rejeite trechos que dependam de contexto anterior (ex: "isso", "essa pergunta", "ali", "aqui", "como eu disse", "entendeu?") sem explicar do que se trata.
    3.2. Valor: Cada candidato precisa ter um takeaway claro (conselho prático, insight, passo-a-passo, ou uma afirmação forte com justificativa). Não retorne frases vazias.
    3.3. Clareza: Prefira segmentos que poderiam ser entendidos por alguém que nunca viu o vídeo inteiro.
    4. Critério de Viralidade: Procure por ganchos (hooks) fortes, curiosidades, emoção intensa ou conselhos práticos.
    5. Escassez de Notas Altas: Seja rigoroso. A maioria dos clips deve ser nota 6 ou 7. Apenas ouro puro recebe 9 ou 10.

    COBERTURA E VARIEDADE (MUITO IMPORTANTE):
    - Gere uma lista de candidatos maior e bem distribuída ao longo de TODO o vídeo.
    - Evite retornar apenas 1-2 candidatos. Retorne o máximo possível de candidatos válidos (idealmente 12-25), desde que respeitem as regras.
    - Evite candidatos sobrepostos (mantenha uma distância mínima de ~5s entre candidatos quando possível).

    FOLGA NO FINAL DO CORTE:
    - Para evitar cortes “em cima” do fim da fala, faça o `end_time` terminar ~1.0s DEPOIS do final natural do segmento,
      desde que isso ainda use timestamps existentes e respeite a duração máxima.

    REGRAS DE FORMATAÇÃO NUMÉRICA:
    Para todos os campos numéricos (start_time, end_time, engagement_score):

    - start_time e end_time: podem ser inteiros ou decimais, mas NÃO use .0 desnecessário.
    - engagement_score: SEMPRE retorne decimal com 2 casas (ex: 7.34, 8.50, 6.05). Evite notas “redondas”.
    - Use a escala 0-10, e use toda a faixa (ex: 5.80, 6.45, 7.12, 8.63, 9.41).

    FORMATO DO TEXTO DO CANDIDATO:
    - Em `text`, inclua o trecho completo do clip (não apenas a frase final).
    - Evite recortes que comecem/terminem no meio da ideia.
    """

    if language.startswith("pt"):
        prompt = f"""{base_instructions}
        Idioma do Vídeo: Português.

        SAÍDA:
        - Retorne APENAS JSON válido (sem markdown, sem ```json, sem comentários, sem texto extra).
        - Não inclua caracteres antes do '{{' nem depois do '}}'.

        Retorne um JSON com:
        1. title: Título viral para o vídeo original.
        2. description: Descrição SEO.
        3. candidates: Lista dos melhores clips.
        
        Transcrição Formatada:
        {formatted_text}"""
    else:
        prompt = f"""
    You are a world-class video editor and viral content strategist.
    Analyze the provided transcript (containing timestamps in [start-end] format).
    Your mission is to identify segments with the highest viral potential for Shorts, Reels, and TikTok.

    CRITICAL ANALYSIS GUIDELINES:
    1. Exact Timestamps: STRICTLY use the timestamps provided in the text (`start_time` and `end_time`). NEVER hallucinate or invent times that do not exist in the transcript.
    2. Duration: Clips must be between {min_duration} and {max_duration} seconds.
    3. Context: Select only segments that have a logical beginning, middle, and end (stand-alone context).
    4. Virality Criteria: Look for strong hooks, curiosity gaps, intense emotion, or practical advice.
    5. High Score Scarcity: Be rigorous. Most clips should be a 6 or 7. Only pure gold gets a 9 or 10.

    NUMERIC FORMATTING RULES:
    For all numeric fields (start_time, end_time, engagement_score):
    - start_time and end_time: can be integers or decimals, but do NOT use .0 unnecessarily.
    - engagement_score: ALWAYS return a decimal with 2 digits (e.g., 7.34, 8.50, 6.05). Avoid round scores.
    - Use a 0-10 scale and use the full range.

    Return JSON with:
    1. title: Viral title for original video.
    2. description: SEO Description.
    3. candidates: List of best clips.

    Formatted Transcript:
    {formatted_text}"""

    try:
        # Modelo mais barato possível
        model_name = "gemini-2.5-flash-lite"
        
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.4,
                max_output_tokens=8192,
            )
        )

        raw_text = _get_gemini_response_text(response)
        logger.info(
            "Gemini response received: chars=%s",
            len(raw_text) if isinstance(raw_text, str) else "<non-str>",
        )

        try:
            analysis_data = _safe_load_json_response(raw_text)
        except json.JSONDecodeError:
            logger.warning(
                "Gemini response not valid JSON. preview=%r",
                (raw_text[:500] if isinstance(raw_text, str) else str(raw_text)[:500]),
            )
            try:
                analysis_data = _repair_gemini_json(model, raw_text, response_schema)
            except json.JSONDecodeError:
                logger.error(
                    "Gemini JSON repair failed. preview=%r",
                    (raw_text[:500] if isinstance(raw_text, str) else str(raw_text)[:500]),
                )
                raise

        logger.info(f"Análise Gemini concluída: {len(analysis_data.get('candidates', []))} clips identificados")
        return analysis_data

    except Exception as e:
        logger.error(f"Erro na chamada Gemini: {e}")
        raise Exception(f"Falha na IA Generativa: {e}")


def _safe_load_json_response(text: str) -> dict:
    if not isinstance(text, str):
        raise json.JSONDecodeError("Response text is not a string", str(text), 0)

    raw = text.strip()
    if not raw:
        raise json.JSONDecodeError("Empty response text", raw, 0)

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("JSON root is not an object", raw[:5000], 0)
        return parsed
    except json.JSONDecodeError:
        pass

    fenced = _extract_json_from_fences(raw)
    if fenced is not None:
        try:
            parsed = json.loads(fenced)
            if not isinstance(parsed, dict):
                raise json.JSONDecodeError("JSON root is not an object", fenced[:5000], 0)
            return parsed
        except json.JSONDecodeError:
            pass

    extracted = _extract_first_json_value(raw)
    if extracted is not None:
        parsed = json.loads(extracted)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("JSON root is not an object", extracted[:5000], 0)
        return parsed

    preview = raw[:5000]
    raise json.JSONDecodeError("Could not extract valid JSON from response", preview, 0)


def _get_gemini_response_text(response) -> str:
    """Best-effort to extract text from google.generativeai response object."""
    t = getattr(response, "text", None)
    if isinstance(t, str) and t.strip():
        return t

    # Fallback: candidates[*].content.parts[*].text
    candidates = getattr(response, "candidates", None) or []
    parts: list[str] = []
    for c in candidates:
        content = getattr(c, "content", None)
        if not content:
            continue
        for p in getattr(content, "parts", None) or []:
            pt = getattr(p, "text", None)
            if isinstance(pt, str) and pt.strip():
                parts.append(pt)

    return "\n".join(parts).strip()


def _repair_gemini_json(model, raw_text: str, response_schema: dict) -> dict:
    """Second-pass: ask Gemini to output valid JSON only.

    This mitigates cases where the first response includes extra text, is wrapped,
    or has minor JSON formatting issues.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise json.JSONDecodeError("Empty response text", str(raw_text), 0)

    repair_prompt = (
        "Converta o conteúdo abaixo em JSON VÁLIDO que siga exatamente o schema. "
        "Retorne APENAS o JSON (sem markdown, sem texto extra).\n\n"
        "CONTEÚDO:\n"
        f"{raw_text}"
    )

    repair_response = model.generate_content(
        repair_prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.0,
            max_output_tokens=4096,
        ),
    )

    repaired_text = _get_gemini_response_text(repair_response)
    return _safe_load_json_response(repaired_text)


def _extract_json_from_fences(text: str) -> str | None:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    fenced = m.group(1).strip()
    extracted = _extract_first_json_value(fenced)
    return extracted.strip() if extracted is not None else fenced


def _extract_first_json_value(text: str) -> str | None:
    obj_start = text.find("{")
    arr_start = text.find("[")

    if obj_start == -1 and arr_start == -1:
        return None

    if obj_start == -1:
        start = arr_start
        open_ch = "["
        close_ch = "]"
    elif arr_start == -1:
        start = obj_start
        open_ch = "{"
        close_ch = "}"
    else:
        start = obj_start if obj_start < arr_start else arr_start
        open_ch = "{" if start == obj_start else "["
        close_ch = "}" if open_ch == "{" else "]"

    in_string = False
    escape = False
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1].strip()

    return None


def _get_duration_bounds(video_id: str) -> tuple[int, int]:
    try:
        from ..models import Job
        job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
        cfg = (job.configuration if job else None) or {}

        max_d = cfg.get("max_clip_duration") or cfg.get("maxDuration")
        if max_d is None:
            max_d = 60
        max_d = int(max(10, min(int(max_d), 180)))

        min_d = cfg.get("min_clip_duration") or cfg.get("minDuration")
        if min_d is None:
            min_d = max(10, int(round(max_d * 0.6)))
        min_d = int(max(5, min(int(min_d), max_d)))

        return min_d, max_d
    except Exception:
        return 10, 60