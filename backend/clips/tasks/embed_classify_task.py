import logging
from celery import shared_task
from django.conf import settings
import numpy as np
from numpy.linalg import norm
import google.generativeai as genai

from ..models import Video, Transcript, Organization
from ..services.embedding_cache_service import EmbeddingCacheService
from .job_utils import update_job_status

logger = logging.getLogger(__name__)

_DEFAULT_VIRAL_EMBEDDING = None


@shared_task(bind=True, max_retries=5)
def embed_classify_task(self, video_id: str) -> dict:
    try:
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "embedding"
        video.current_step = "embedding"
        video.save()
        update_job_status(str(video.video_id), "embedding", progress=55, current_step="embedding")

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not candidates:
            logger.warning(f"Sem candidatos para embedding no vídeo {video_id}")
        else:
            api_key = getattr(settings, "GEMINI_API_KEY", None)
            if not api_key:
                raise Exception("GEMINI_API_KEY não configurada")

            genai.configure(api_key=api_key)

            texts = [c.get("text", "") for c in candidates if c.get("text")]
            
            if texts:
                embeddings = _get_batch_embeddings(texts)
                
                reference_patterns = _get_reference_patterns(org.organization_id)

                text_idx = 0
                for candidate in candidates:
                    if not candidate.get("text"):
                        continue
                    
                    try:
                        embedding = embeddings[text_idx]
                        text_idx += 1
                        
                        candidate["embedding"] = embedding
                        
                        similarity_score = _calculate_similarity(embedding, reference_patterns)
                        candidate["similarity_score"] = similarity_score
                        
                        engagement_score = int(candidate.get("engagement_score", 0) * 10)
                        candidate["adjusted_engagement_score"] = _adjust_score(
                            engagement_score=engagement_score,
                            similarity_score=similarity_score,
                        )
                    except Exception as e:
                        logger.warning(f"Falha ao processar métricas do candidato: {e}")

        transcript.analysis_data = analysis_data
        transcript.save()

        video.last_successful_step = "embedding"
        video.status = "selecting"
        video.current_step = "selecting"
        video.save()
        
        update_job_status(str(video.video_id), "selecting", progress=60, current_step="selecting")

        from .select_clips_task import select_clips_task
        select_clips_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.select.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "status": "selecting",
            "candidates_processed": len(candidates),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro no embedding {video_id}: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _get_batch_embeddings(texts: list[str], output_dimensionality: int = 768) -> list[list]:
    if not texts:
        return []

    final_embeddings = [None] * len(texts)
    
    texts_to_process = []
    indices_to_process = []
    
    for idx, text in enumerate(texts):
        cached = EmbeddingCacheService.get_embedding(text)
        if cached:
            final_embeddings[idx] = cached
        else:
            texts_to_process.append(text)
            indices_to_process.append(idx)
    
    if not texts_to_process:
        return final_embeddings
    
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=texts_to_process,
            task_type="SEMANTIC_SIMILARITY"
        )
        
        embedding_list = result.get('embedding', []) if isinstance(result, dict) else result.embeddings

        for i, embedding_obj in enumerate(embedding_list):
            if hasattr(embedding_obj, 'values'):
                vals = embedding_obj.values
            elif isinstance(embedding_obj, dict):
                vals = embedding_obj.get('values')
            else:
                vals = embedding_obj
            
            normalized = _normalize_embedding(vals)
            
            original_idx = indices_to_process[i]
            final_embeddings[original_idx] = normalized
            
            EmbeddingCacheService.save_embedding(texts_to_process[i], normalized)
        
        return final_embeddings

    except Exception as e:
        logger.error(f"Erro na API Gemini Embedding: {e}")
        raise e


def _normalize_embedding(embedding: list) -> list:
    try:
        embedding_np = np.array(embedding, dtype=np.float32)
        embedding_norm = norm(embedding_np)
        if embedding_norm == 0:
            return embedding
        return (embedding_np / embedding_norm).tolist()
    except:
        return embedding


def _get_reference_patterns(organization_id: str) -> list:
    try:
        from ..models import EmbeddingPattern
        patterns = list(EmbeddingPattern.objects.filter(
            organization_id=organization_id
        ).values_list('embedding', flat=True)[:10])
        
        if patterns:
            return [
                (np.array(p, dtype=np.float32) / (norm(np.array(p, dtype=np.float32)) or 1.0))
                for p in patterns
            ]
            
    except Exception as e:
        logger.warning(f"Erro ao carregar padrões da org: {e}")

    return [_get_default_viral_embedding()]


def _get_default_viral_embedding() -> np.ndarray:
    global _DEFAULT_VIRAL_EMBEDDING
    if _DEFAULT_VIRAL_EMBEDDING is not None:
        return _DEFAULT_VIRAL_EMBEDDING
    
    viral_concept = "Viral video, funny moment, engaging clip, high retention, interesting fact, emotional hook"
    
    try:
        embeds = _get_batch_embeddings([viral_concept])
        if embeds and embeds[0]:
            _DEFAULT_VIRAL_EMBEDDING = np.array(embeds[0], dtype=np.float32)
            return _DEFAULT_VIRAL_EMBEDDING
    except Exception as e:
        logger.error(f"Falha ao gerar embedding viral padrão: {e}")
    
    return np.random.randn(768).astype(np.float32)


def _calculate_similarity(embedding: list, reference_patterns: list) -> float:
    if not embedding or not reference_patterns:
        return 0.5

    try:
        embedding_np = np.array(embedding, dtype=np.float32)
        
        similarities = [
            np.dot(embedding_np, pattern) for pattern in reference_patterns
        ]
        
        score = np.mean(similarities)
        
        normalized = (score + 1.0) / 2.0
        
        return float(np.clip(normalized, 0.0, 1.0))
    except Exception as e:
        logger.warning(f"Erro cálculo similaridade: {e}")
        return 0.5


def _adjust_score(engagement_score: int, similarity_score: float) -> int:
    adjusted = (engagement_score * 0.7) + (similarity_score * 100 * 0.3)
    return int(np.clip(adjusted, 0, 100))
