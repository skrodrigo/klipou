import json
import logging
from celery import shared_task
from django.conf import settings
import google.generativeai as genai

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status

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

        analysis_result = _analyze_with_gemini(formatted_text, language)

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
            queue=f"video.classify.{org.plan}",
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

            if self.request.retries < self.max_retries:
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


def _analyze_with_gemini(formatted_text: str, language: str) -> dict:
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
                        "engagement_score": {"type": "integer"},
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
    
    base_instructions = """
    Você é um especialista em edição de vídeo e conteúdo viral.
    Analise a transcrição fornecida (com timestamps [início-fim]).
    Identifique os segmentos mais engajantes para shorts (Shorts/Reels/TikTok).
    
    CRÍTICO:
    - Use os timestamps EXATOS fornecidos no texto para start_time e end_time.
    - Não invente timestamps.
    - Clips devem ter entre 15 e 60 segundos.
    - Selecione segmentos que façam sentido sozinhos.
    """

    if language.startswith("pt"):
        prompt = f"""{base_instructions}
        
        Retorne um JSON com:
        1. title: Título viral para o vídeo original.
        2. description: Descrição SEO.
        3. candidates: Lista dos melhores clips.
        
        Transcrição Formatada:
        {formatted_text}"""
    else:
        prompt = f"""
    You are an expert video editor and viral content strategist.
    Analyze the provided transcript (with timestamps [start-end]).
    Identify the most engaging segments for shorts (Shorts/Reels/TikTok).
    
    CRITICAL:
    - Use the EXACT timestamps provided in the text for start_time and end_time.
    - Do not invent timestamps.
    - Clips should be between 15 and 60 seconds.
    - Select segments that stand alone.
    
    Return JSON with:
    1. title: Viral title for original video.
    2. description: SEO Description.
    3. candidates: List of best clips.
    
    Formatted Transcript:
    {formatted_text}"""

    try:
        model_name = "gemini-flash-latest"
        
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.4
            )
        )
        
        analysis_data = json.loads(response.text)
        logger.info(f"Análise Gemini concluída: {len(analysis_data.get('candidates', []))} clips identificados")
        return analysis_data

    except Exception as e:
        logger.error(f"Erro na chamada Gemini: {e}")
        raise Exception(f"Falha na IA Generativa: {e}")
