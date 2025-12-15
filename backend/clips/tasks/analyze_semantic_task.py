"""
Task para análise semântica com Gemini.
Etapa: Analyzing
Envia apenas texto da transcrição (nunca vídeo).
"""

import json
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript
import google.generativeai as genai


@shared_task(bind=True, max_retries=5)
def analyze_semantic_task(self, video_id: int) -> dict:
    """
    Análise semântica com Gemini API.
    
    Gemini retorna:
    - Título do vídeo (título sugerido para o vídeo original)
    - Descrição (descrição para publicação)
    - Trechos candidatos (segmentos com timestamps)
    - Score de engajamento (0-10 para cada trecho)
    - Possíveis hooks/títulos (para cada clip)
    - Análise de tom/emoção
    """
    try:
        video = Video.objects.get(id=video_id)
        video.status = "analyzing"
        video.current_step = "analyzing"
        video.save()

        # Obtém transcrição
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        # Prepara prompt para Gemini
        full_text = transcript.full_text
        language = transcript.language

        # Chama Gemini
        analysis_result = _analyze_with_gemini(full_text, language)

        # Armazena análise na transcrição
        transcript.analysis_data = analysis_result
        transcript.save()

        # Atualiza vídeo
        video.last_successful_step = "analyzing"
        video.save()

        return {
            "video_id": video_id,
            "status": "analyzing",
            "title": analysis_result.get("title"),
            "description": analysis_result.get("description"),
            "candidates_count": len(analysis_result.get("candidates", [])),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "analyzing"
        video.error_code = "ANALYSIS_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _analyze_with_gemini(full_text: str, language: str) -> dict:
    """Analisa texto com Gemini API."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise Exception("GEMINI_API_KEY não configurada")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Prompt em português ou inglês
    if language.startswith("pt"):
        prompt = f"""Analise este texto de vídeo e retorne um JSON com:
1. title: Título sugerido para o vídeo (máx 100 caracteres)
2. description: Descrição para publicação (máx 300 caracteres)
3. candidates: Array de trechos candidatos a clips com:
   - text: Texto do trecho
   - start_time: Tempo de início estimado (em segundos, aproximado)
   - end_time: Tempo de fim estimado (em segundos, aproximado)
   - engagement_score: Score de engajamento (0-10)
   - hook_title: Título/hook sugerido para este clip
   - tone: Tom/emoção (positivo, negativo, neutro, inspirador, etc)
4. overall_tone: Tom geral do vídeo
5. key_topics: Array de tópicos principais

Retorne APENAS o JSON, sem markdown ou explicações.

Texto:
{full_text}"""
    else:
        prompt = f"""Analyze this video text and return a JSON with:
1. title: Suggested title for the video (max 100 characters)
2. description: Description for publication (max 300 characters)
3. candidates: Array of clip candidate segments with:
   - text: Segment text
   - start_time: Estimated start time (in seconds, approximate)
   - end_time: Estimated end time (in seconds, approximate)
   - engagement_score: Engagement score (0-10)
   - hook_title: Suggested title/hook for this clip
   - tone: Tone/emotion (positive, negative, neutral, inspiring, etc)
4. overall_tone: Overall tone of the video
5. key_topics: Array of main topics

Return ONLY the JSON, without markdown or explanations.

Text:
{full_text}"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Remove markdown code blocks se presentes
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        analysis_data = json.loads(response_text)
        return analysis_data

    except json.JSONDecodeError as e:
        raise Exception(f"Gemini retornou JSON inválido: {e}")
    except Exception as e:
        raise Exception(f"Erro ao chamar Gemini: {e}")
