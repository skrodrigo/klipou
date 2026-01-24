import json
import logging
import re
import hashlib
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from google import genai
from google.genai import types

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status, get_plan_tier

logger = logging.getLogger(__name__)

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client:
        return _gemini_client

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _transcript_hash(transcript: Transcript) -> str:
    segments = transcript.segments or []
    full_text = transcript.full_text or ""

    h = hashlib.sha256()
    h.update(str(transcript.video_id).encode("utf-8"))
    h.update(b"\n")
    h.update(str(transcript.language or "").encode("utf-8"))
    h.update(b"\n")
    h.update(str(len(segments)).encode("utf-8"))
    h.update(b"\n")
    h.update(full_text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _should_skip_gemini_analysis(transcript: Transcript, cfg: dict) -> bool:
    analysis_data = transcript.analysis_data or {}
    meta = analysis_data.get("meta") if isinstance(analysis_data, dict) else None
    if not isinstance(meta, dict):
        return False

    if meta.get("transcript_hash") != _transcript_hash(transcript):
        return False

    # If you change prompt semantics/config, bump this.
    if meta.get("analysis_version") != 2:
        return False

    # If duration bounds/config changed, re-run.
    if meta.get("config") != cfg:
        return False

    candidates = analysis_data.get("candidates")
    return isinstance(candidates, list) and len(candidates) > 0


def _format_transcript_with_timestamps(segments: list) -> str:
    if not segments:
        return ""

    buffer = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = (seg.get("text") or "").strip()
        try:
            buffer.append(f"[{float(start):.1f}-{float(end):.1f}] {text}")
        except Exception:
            buffer.append(f"[{start}-{end}] {text}")

    return "\n".join(buffer)


def _clean_number(num):
    """Converte 10.0 para 10 (int), mas mantém 5.8 (float)."""
    try:
        f_num = float(num)
        if f_num.is_integer():
            return int(f_num)
        return f_num
    except Exception:
        return num


def _chunk_segments_by_time(segments: list, chunk_seconds: int) -> list[list[dict]]:
    if not segments or not chunk_seconds or chunk_seconds <= 0:
        return []

    chunks: list[list[dict]] = []
    current: list[dict] = []
    chunk_start: float | None = None

    for seg in segments:
        if not isinstance(seg, dict):
            continue

        start = seg.get("start")
        end = seg.get("end")
        try:
            start_f = float(start) if start is not None else None
        except Exception:
            start_f = None
        try:
            end_f = float(end) if end is not None else None
        except Exception:
            end_f = None

        if start_f is None:
            # Can't chunk reliably without timestamps; fall back to a single chunk.
            return [s for s in [segments] if s]

        if chunk_start is None:
            chunk_start = start_f

        boundary = end_f if end_f is not None else start_f
        if boundary - chunk_start > float(chunk_seconds) and current:
            chunks.append(current)
            current = []
            chunk_start = start_f

        current.append(seg)

    if current:
        chunks.append(current)

    return chunks


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

        segments = transcript.segments or []
        language = transcript.language

        min_d, max_d = _get_duration_bounds(video_id=str(video.video_id))

        # Job-level preferences (optional)
        max_clips_desired = int(getattr(settings, "MAX_CLIPS_DESIRED", 25) or 25)
        try:
            from ..models import Job
            job = Job.objects.filter(video_id=str(video.video_id)).order_by("-created_at").first()
            cfg = (job.configuration if job else None) or {}
            max_clips_desired = int(cfg.get("max_clips_desired") or cfg.get("maxClips") or max_clips_desired)
        except Exception:
            cfg = {}

        # Clamp hardcap
        max_clips_desired = int(max(3, min(max_clips_desired, 25)))

        analyze_cfg = {
            "min_duration": int(min_d),
            "max_duration": int(max_d),
            "max_clips_desired": int(max_clips_desired),
        }

        if _should_skip_gemini_analysis(transcript, analyze_cfg):
            analysis_result = transcript.analysis_data or {}
            logger.info(
                "[analyze] cache hit video_id=%s transcript_hash=%s",
                str(video.video_id),
                (analysis_result.get("meta") or {}).get("transcript_hash"),
            )
        else:
            analysis_result = _analyze_transcript_with_gemini(
                segments,
                language,
                min_duration=min_d,
                max_duration=max_d,
                video_duration_s=float(video.duration or 0) if video else 0,
                video_id=str(video.video_id),
                organization_id=str(org.organization_id),
                max_clips_desired=max_clips_desired,
            )

        if isinstance(analysis_result, dict):
            existing_meta = analysis_result.get("meta")
            if not isinstance(existing_meta, dict):
                existing_meta = {}

            # Do not drop meta produced by chunk merge (e.g. fillers_dropped).
            analysis_result["meta"] = {
                **existing_meta,
                "analysis_version": 2,
                "transcript_hash": _transcript_hash(transcript),
                "config": analyze_cfg,
            }

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

            update_job_status(str(video.video_id), "failed", progress=100, current_step="analyzing")

            msg = str(e)
            non_retryable = (
                "Could not extract valid JSON" in msg
                or "Empty response text" in msg
                or "Response text is not a string" in msg
            )

            if not non_retryable and self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _analyze_transcript_with_gemini(
    segments: list,
    language: str,
    min_duration: int,
    max_duration: int,
    video_duration_s: float,
    video_id: str,
    organization_id: str,
    max_clips_desired: int,
) -> dict:
    enable_chunking = bool(getattr(settings, "GEMINI_ANALYZE_ENABLE_CHUNKING", True))
    chunk_seconds = int(getattr(settings, "GEMINI_ANALYZE_CHUNK_SECONDS", 600) or 600)
    chunk_threshold_seconds = int(getattr(settings, "GEMINI_ANALYZE_CHUNK_THRESHOLD_SECONDS", 1800) or 1800)

    formatted_text = _format_transcript_with_timestamps(segments)

    should_chunk = False
    if enable_chunking and chunk_seconds > 0:
        if isinstance(video_duration_s, (int, float)) and video_duration_s and video_duration_s >= chunk_threshold_seconds:
            should_chunk = True
        elif len(formatted_text) >= int(getattr(settings, "GEMINI_ANALYZE_CHUNK_THRESHOLD_CHARS", 45000) or 45000):
            should_chunk = True

    if not should_chunk:
        return _analyze_with_gemini(
            formatted_text,
            language,
            min_duration=min_duration,
            max_duration=max_duration,
            organization_id=organization_id,
            max_candidates=max_clips_desired,
        )

    chunks = _chunk_segments_by_time(segments, chunk_seconds)
    if not chunks:
        return _analyze_with_gemini(
            formatted_text,
            language,
            min_duration=min_duration,
            max_duration=max_duration,
            organization_id=organization_id,
            max_candidates=max_clips_desired,
        )

    merged_candidates: list[dict] = []
    merged_title: str | None = None
    merged_description: str | None = None
    merged_overall_tone: str | None = None
    merged_key_topics: list[str] = []

    fillers_dropped = 0

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        update_job_status(
            str(video_id),
            "analyzing",
            progress=45 + int(((i) / max(1, total)) * 4),
            current_step=f"analyzing_chunk_{i+1}/{total}",
        )

        chunk_text = _format_transcript_with_timestamps(chunk)
        if not chunk_text.strip():
            continue

        try:
            chunk_result = _analyze_with_gemini(
                chunk_text,
                language,
                min_duration=min_duration,
                max_duration=max_duration,
                organization_id=organization_id,
                max_candidates=max(10, min(20, max_clips_desired)),
            )
        except Exception as e:
            logger.warning(
                "Falha no chunk Gemini %s/%s para video_id=%s: %s",
                i + 1,
                total,
                video_id,
                e,
            )
            continue

        if not merged_title:
            t = (chunk_result or {}).get("title")
            if isinstance(t, str) and t.strip():
                merged_title = t.strip()
        if not merged_description:
            d = (chunk_result or {}).get("description")
            if isinstance(d, str) and d.strip():
                merged_description = d.strip()
        if not merged_overall_tone:
            ot = (chunk_result or {}).get("overall_tone")
            if isinstance(ot, str) and ot.strip():
                merged_overall_tone = ot.strip()

        kt = (chunk_result or {}).get("key_topics") or []
        if isinstance(kt, list):
            for item in kt:
                if isinstance(item, str) and item.strip() and item.strip() not in merged_key_topics:
                    merged_key_topics.append(item.strip())

        cand = (chunk_result or {}).get("candidates") or []
        if isinstance(cand, list):
            for c in cand:
                if not isinstance(c, dict):
                    continue
                cat = (c.get("category") or "").strip().upper()
                if cat == "FILLER":
                    fillers_dropped += 1
                    continue
                merged_candidates.append(c)

    if not merged_candidates:
        raise RuntimeError("Falha ao analisar todos os chunks com Gemini (nenhum candidato retornado).")

    # Hardcap overall output
    try:
        merged_candidates.sort(key=lambda c: float(c.get("engagement_score", 0) or 0), reverse=True)
    except Exception:
        pass

    merged_candidates = merged_candidates[: int(max_clips_desired)]

    out = {
        "title": merged_title or "",
        "description": merged_description or "",
        "candidates": merged_candidates,
        "overall_tone": merged_overall_tone or "",
        "key_topics": merged_key_topics,
    }

    out["meta"] = {
        "chunks_total": total,
        "fillers_dropped": fillers_dropped,
    }

    return out


def _analyze_with_gemini(
    formatted_text: str,
    language: str,
    min_duration: int,
    max_duration: int,
    organization_id: str,
    max_candidates: int,
) -> dict:
    client = _get_gemini_client()

    _enforce_gemini_rate_limit(organization_id=organization_id, kind="analyze")

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
                        "category": {
                            "type": "string",
                            "enum": ["MUST_HAVE", "GOOD", "FILLER"],
                        },
                    },
                    "required": ["text", "start_time", "end_time", "engagement_score", "hook_title", "tone", "category"]
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

    max_candidates = int(max(5, min(int(max_candidates or 15), 25)))

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

    QUANTIDADE E QUALIDADE (CRÍTICO):
    - Retorne NO MÁXIMO {max_candidates} candidatos.
    - Priorize QUALIDADE sobre quantidade.
    - Classifique cada candidato em uma categoria:
      - MUST_HAVE: 8.0 a 10.0 (muito forte)
      - GOOD: 6.0 a 7.9 (bom)
      - FILLER: 4.0 a 5.9 (só se faltar opção)
    - Seja consistente: engagement_score é RELATIVO dentro do contexto do vídeo (não absoluto global).

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

    model_name = "gemini-2.5-flash-lite"

    max_output_tokens = int(getattr(settings, "GEMINI_ANALYZE_MAX_OUTPUT_TOKENS", 12288) or 12288)

    response = client.models.generate_content(
        model=f'models/{model_name}',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.4,
            max_output_tokens=max_output_tokens,
        )
    )

    _log_gemini_usage(response, organization_id=organization_id, kind="analyze", model=model_name)

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
            analysis_data = _repair_gemini_json(client, raw_text, response_schema)
        except json.JSONDecodeError:
            logger.error(
                "Gemini JSON repair failed. preview=%r",
                (raw_text[:500] if isinstance(raw_text, str) else str(raw_text)[:500]),
            )
            raise

    try:
        cands = analysis_data.get("candidates") or []
        if isinstance(cands, list):
            # Keep max_candidates from this call.
            analysis_data["candidates"] = cands[:max_candidates]
    except Exception:
        pass

    logger.info(f"Análise Gemini concluída: {len(analysis_data.get('candidates', []))} clips identificados")
    return analysis_data


def _safe_load_json_response(text: str) -> dict:
    if not isinstance(text, str):
        raise json.JSONDecodeError("Response text is not a string", str(text), 0)

    raw = text.replace("\ufeff", "").replace("\x00", "").strip()
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

    if "{" in raw and "}" in raw:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if 0 <= start < end:
                candidate = raw[start : end + 1].strip()
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    preview = raw[:5000]
    raise json.JSONDecodeError("Could not extract valid JSON from response", preview, 0)


def _get_gemini_response_text(response) -> str:
    """Best-effort to extract text from gemini response object."""
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


def _repair_gemini_json(client, raw_text: str, response_schema: dict) -> dict:
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

    repair_response = client.models.generate_content(
        model='models/gemini-2.5-flash-lite',
        contents=repair_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.0,
            max_output_tokens=int(getattr(settings, "GEMINI_ANALYZE_REPAIR_MAX_OUTPUT_TOKENS", 8192) or 8192),
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


def _enforce_gemini_rate_limit(organization_id: str, kind: str) -> None:
    """Simple sliding window limiter via Redis cache.

    Defaults: 60 calls/minute per org per kind.
    """
    org_key = (organization_id or "unknown").strip()
    k = (kind or "generic").strip().lower()

    window_seconds = int(getattr(settings, "GEMINI_RATE_LIMIT_WINDOW_SECONDS", 60) or 60)
    max_calls = int(getattr(settings, "GEMINI_RATE_LIMIT_MAX_CALLS", 60) or 60)

    cache_key = f"gemini_rl:{k}:{org_key}"
    try:
        cache.add(cache_key, 0, timeout=window_seconds)
        current = cache.incr(cache_key)
    except Exception:
        # If cache is unavailable, do not block the pipeline.
        return

    if int(current) > int(max_calls):
        raise RuntimeError(f"Rate limit Gemini excedido (org={org_key} kind={k}). Tente novamente em instantes.")


def _log_gemini_usage(response, organization_id: str, kind: str, model: str) -> None:
    try:
        usage = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
        if usage is None:
            return

        prompt_tokens = getattr(usage, "prompt_token_count", None) or getattr(usage, "promptTokenCount", None)
        output_tokens = getattr(usage, "candidates_token_count", None) or getattr(usage, "candidatesTokenCount", None)
        total_tokens = getattr(usage, "total_token_count", None) or getattr(usage, "totalTokenCount", None)

        logger.info(
            "[gemini_usage] org=%s kind=%s model=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
            organization_id,
            kind,
            model,
            prompt_tokens,
            output_tokens,
            total_tokens,
        )
    except Exception:
        return