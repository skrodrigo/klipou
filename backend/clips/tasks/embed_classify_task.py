import logging
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
import numpy as np
from numpy.linalg import norm
import json
from google import genai
from google.genai import types

from ..models import Video, Transcript, Organization
from ..services.embedding_cache_service import EmbeddingCacheService
from .job_utils import get_plan_tier, update_job_status

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
            client = _get_gemini_client()
            
            texts = [c.get("text", "") for c in candidates if c.get("text")]
            
            if texts:
                embeddings = _get_batch_embeddings(client, texts, organization_id=str(org.organization_id))
                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        f"Embeddings ({len(embeddings)}) != Texts ({len(texts)})"
                    )
                
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
            queue=f"video.select.{get_plan_tier(org.plan)}",
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

            update_job_status(str(video.video_id), "failed", progress=100, current_step="embedding")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _get_batch_embeddings(client, texts: list[str], organization_id: str = "", output_dimensionality: int = 768) -> list[list]:
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
        batch_size = int(getattr(settings, "GEMINI_EMBED_BATCH_SIZE", 100) or 100)
        if batch_size <= 0:
            batch_size = 100

        total = len(texts_to_process)
        total_batches = (total - 1) // batch_size + 1

        for batch_i, start in enumerate(range(0, total, batch_size)):
            end = min(start + batch_size, total)
            batch_texts = texts_to_process[start:end]
            batch_indices = indices_to_process[start:end]

            logger.info(
                "Processando batch embeddings %s/%s (%s textos)",
                batch_i + 1,
                total_batches,
                len(batch_texts),
            )

            _enforce_gemini_rate_limit(organization_id=organization_id, kind="embed")

            response = client.models.embed_content(
                model="text-embedding-004",
                contents=batch_texts,
                config=types.EmbedContentConfig(output_dimensionality=output_dimensionality),
            )

            _log_gemini_usage(response, organization_id=organization_id, kind="embed", model="text-embedding-004")

            embedding_list = _extract_embedding_values(response)
            if len(embedding_list) != len(batch_texts):
                raise RuntimeError(
                    f"Resposta inesperada do Gemini Embedding: expected={len(batch_texts)} got={len(embedding_list)}"
                )

            for i, vals in enumerate(embedding_list):
                if not vals:
                    continue

                normalized = _normalize_embedding(vals)

                original_idx = batch_indices[i]
                final_embeddings[original_idx] = normalized

                EmbeddingCacheService.save_embedding(batch_texts[i], normalized)
        
        return final_embeddings

    except Exception as e:
        logger.error(f"Erro na API Gemini Embedding: {e}")
        raise e


def _extract_embedding_values(response) -> list[list]:
    def _to_mapping(obj):
        if isinstance(obj, dict):
            return obj
        return None

    def _get_vals(embedding_obj):
        if embedding_obj is None:
            return None
        if isinstance(embedding_obj, dict):
            return embedding_obj.get("values") or embedding_obj.get("value")
        vals = getattr(embedding_obj, "values", None)
        if vals is not None:
            return vals
        return getattr(embedding_obj, "value", None)

    resp_map = _to_mapping(response)

    embeddings = None
    if resp_map is not None:
        embeddings = resp_map.get("embeddings") or resp_map.get("embedding")
    else:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None:
            embeddings = getattr(response, "embedding", None)

    if embeddings is None:
        return []

    if not isinstance(embeddings, list):
        embeddings = [embeddings]

    out: list[list] = []
    for e in embeddings:
        vals = _get_vals(e)
        out.append(list(vals) if vals is not None else [])
    return out


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
            try:
                parsed_patterns = []
                for p in patterns:
                    if isinstance(p, str):
                        parsed_patterns.append(json.loads(p))
                    elif isinstance(p, list):
                        parsed_patterns.append(p)

                return [
                    (np.array(p_list, dtype=np.float32) / (norm(np.array(p_list, dtype=np.float32)) or 1.0))
                    for p_list in parsed_patterns
                ]
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to parse pattern embeddings: {e}", exc_info=True)
                # Fallback to default on parsing error
                return [_get_default_viral_embedding()]
            
    except Exception as e:
        logger.warning(f"Error loading organization patterns: {e}", exc_info=True)

    return [_get_default_viral_embedding()]


def _get_default_viral_embedding() -> np.ndarray:
    global _DEFAULT_VIRAL_EMBEDDING
    if _DEFAULT_VIRAL_EMBEDDING is not None:
        return _DEFAULT_VIRAL_EMBEDDING
    
    viral_concept = "Viral video, funny moment, engaging clip, high retention, interesting fact, emotional hook"
    
    try:
        client = _get_gemini_client()
        embeds = _get_batch_embeddings(client, [viral_concept], organization_id="global")
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


def _get_gemini_client():
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise Exception("GEMINI_API_KEY não configurada")
    return genai.Client(api_key=api_key)


def _enforce_gemini_rate_limit(organization_id: str, kind: str) -> None:
    org_key = (organization_id or "unknown").strip()
    k = (kind or "generic").strip().lower()

    window_seconds = int(getattr(settings, "GEMINI_RATE_LIMIT_WINDOW_SECONDS", 60) or 60)
    max_calls = int(getattr(settings, "GEMINI_RATE_LIMIT_MAX_CALLS", 60) or 60)

    cache_key = f"gemini_rl:{k}:{org_key}"
    try:
        cache.add(cache_key, 0, timeout=window_seconds)
        current = cache.incr(cache_key)
    except Exception:
        return

    if int(current) > int(max_calls):
        raise RuntimeError(f"Rate limit Gemini excedido (org={org_key} kind={k}).")


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
