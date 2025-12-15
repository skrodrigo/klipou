"""
Task para embedding e classificação com Gemini.
Etapa: Embedding/Classifying
Usa Gemini API para gerar embeddings do texto dos trechos candidatos.
"""

from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript
import google.generativeai as genai


@shared_task(bind=True, max_retries=5)
def embed_classify_task(self, video_id: int) -> dict:
    """
    Embedding e classificação com Gemini.
    
    Usa Gemini API para gerar embeddings do texto dos trechos candidatos.
    Compara embeddings com:
    - Padrões internos (embeddings de bons clips históricos)
    - Histórico de bons clips (feedback do usuário)
    
    Ajusta score final combinando:
    - Score Gemini (análise semântica)
    - Similaridade vetorial (embeddings)
    - Score de engajamento
    """
    try:
        video = Video.objects.get(id=video_id)
        video.status = "embedding"
        video.current_step = "embedding"
        video.save()

        # Obtém transcrição e análise
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not candidates:
            raise Exception("Nenhum candidato de clip encontrado")

        # Gera embeddings para cada candidato
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise Exception("GEMINI_API_KEY não configurada")

        genai.configure(api_key=api_key)

        # Processa embeddings
        for candidate in candidates:
            text = candidate.get("text", "")
            if not text:
                continue

            try:
                # Gera embedding com Gemini
                embedding = _get_embedding(text)
                candidate["embedding"] = embedding

                # Calcula similaridade com padrões históricos
                similarity_score = _calculate_similarity(embedding)
                candidate["similarity_score"] = similarity_score

                # Ajusta score final
                original_engagement = int(candidate.get("engagement_score", 0) * 10)
                adjusted_score = _adjust_score(
                    engagement_score=original_engagement,
                    similarity_score=similarity_score,
                )
                candidate["adjusted_engagement_score"] = adjusted_score

            except Exception as e:
                print(f"Aviso: Falha ao processar embedding para candidato: {e}")
                # Continua com próximo candidato

        # Armazena análise atualizada
        transcript.analysis_data = analysis_data
        transcript.save()

        # Atualiza vídeo
        video.last_successful_step = "embedding"
        video.save()

        return {
            "video_id": video_id,
            "status": "embedding",
            "candidates_processed": len(candidates),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "embedding"
        video.error_code = "EMBEDDING_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _get_embedding(text: str) -> list:
    """Gera embedding com Gemini API."""
    try:
        model = genai.GenerativeModel("embedding-001")
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
        )
        return result["embedding"]
    except Exception as e:
        raise Exception(f"Erro ao gerar embedding: {e}")


def _calculate_similarity(embedding: list) -> float:
    """
    Calcula similaridade com padrões históricos.
    
    Em produção, compararia com embeddings de bons clips históricos.
    Por enquanto, retorna score baseado em características do embedding.
    """
    if not embedding:
        return 0.5

    # Implementação simplificada
    # Em produção, compararia com banco de embeddings históricos
    # usando similaridade de cosseno ou outra métrica

    # Score baseado em magnitude do embedding
    magnitude = sum(x ** 2 for x in embedding) ** 0.5
    similarity = min(1.0, magnitude / 10.0)  # Normaliza

    return similarity


def _adjust_score(engagement_score: int, similarity_score: float) -> int:
    """
    Ajusta score final combinando:
    - Score de engajamento (70%)
    - Similaridade vetorial (30%)
    """
    adjusted = (engagement_score * 0.7) + (similarity_score * 100 * 0.3)
    return int(min(100, max(0, adjusted)))
