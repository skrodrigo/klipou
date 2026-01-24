import logging
from typing import Optional, List, Any
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
import numpy as np
from numpy.linalg import norm
import json
from google.genai import types

from ..models import Video, Transcript, Organization
from ..services.embedding_cache_service import EmbeddingCacheService
from ..services.gemini_utils import (
    get_gemini_client,
    enforce_gemini_rate_limit,
    log_gemini_usage,
    normalize_score_0_100
)
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100
DEFAULT_OUTPUT_DIMENSIONALITY = 768
DEFAULT_ENGAGEMENT_WEIGHT = 0.7
DEFAULT_SIMILARITY_WEIGHT = 0.3
DEFAULT_FALLBACK_SIMILARITY = 0.5
DEFAULT_VIRAL_CONCEPT = "Viral video, funny moment, engaging clip, high retention, interesting fact, emotional hook"

_DEFAULT_VIRAL_EMBEDDING = None


def _get_config(key: str, default: Any, type_cast=None) -> Any:
    try:
        val = getattr(settings, key, default)
        if val is None:
            return default
        if type_cast:
            return type_cast(val)
        return val
    except (ValueError, TypeError):
        logger.warning(f"Invalid config value for {key}, using default: {default}")
        return default


def _safe_update_job_status(
    video_id: str,
    status: str,
    *,
    progress: Optional[int] = None,
    current_step: Optional[str] = None
):
    try:
        update_job_status(video_id, status, progress=progress, current_step=current_step)
    except Exception as e:
        logger.warning(f"[embed] update_job_status failed for {video_id}: {e}")


def _to_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


@shared_task(bind=True, max_retries=5)
def embed_classify_task(self, video_id: str) -> dict:
    video = None
    
    try:
        logger.info(f"[embed] Iniciando para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "embedding"
        video.current_step = "embedding"
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "embedding",
            progress=55,
            current_step="embedding"
        )

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise ValueError("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not isinstance(candidates, list):
            raise ValueError("Candidates inválidos no analysis_data")

        if not candidates:
            logger.warning(f"[embed] Sem candidatos para video_id={video_id}")
        else:
            client = get_gemini_client()
            
            valid_candidates = [c for c in candidates if isinstance(c, dict)]
            texts = [c.get("text", "") for c in valid_candidates if c.get("text")]
            
            if not texts:
                logger.warning(f"[embed] Nenhum texto válido em candidatos para video_id={video_id}")
            else:
                logger.info(f"[embed] Processando {len(texts)} embeddings")
                
                embeddings = _get_batch_embeddings(
                    client,
                    texts,
                    organization_id=str(org.organization_id)
                )
                
                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        f"Embeddings mismatch: got {len(embeddings)}, expected {len(texts)}"
                    )
                
                reference_patterns = _get_reference_patterns(str(org.organization_id))
                
                logger.info(f"[embed] Usando {len(reference_patterns)} reference patterns")

                embedding_idx = 0
                processed = 0
                failed = 0
                
                for candidate in valid_candidates:
                    if not candidate.get("text"):
                        continue
                    
                    if embedding_idx >= len(embeddings):
                        logger.error(f"[embed] Embedding index out of range: {embedding_idx}")
                        break
                    
                    try:
                        embedding = embeddings[embedding_idx]
                        embedding_idx += 1
                        
                        if not embedding or not isinstance(embedding, list):
                            logger.warning("[embed] Embedding vazio ou inválido, pulando")
                            failed += 1
                            continue
                        
                        expected_dim = _get_config(
                            "GEMINI_EMBED_OUTPUT_DIMENSIONALITY",
                            DEFAULT_OUTPUT_DIMENSIONALITY,
                            int
                        )
                        
                        if len(embedding) != expected_dim:
                            logger.warning(
                                f"[embed] Dimensionalidade incorreta: "
                                f"got {len(embedding)}, expected {expected_dim}"
                            )
                        
                        candidate["embedding"] = embedding
                        
                        similarity_score = _calculate_similarity(embedding, reference_patterns)
                        candidate["similarity_score"] = round(float(similarity_score), 4)
                        
                        score_raw = _to_float(candidate.get("engagement_score"), 0.0)
                        score_0_100 = float(normalize_score_0_100(score_raw))
                        
                        candidate["engagement_score"] = round(score_0_100, 2)
                        
                        adjusted = _adjust_score(
                            engagement_score=score_0_100,
                            similarity_score=similarity_score,
                        )
                        candidate["adjusted_engagement_score"] = round(float(adjusted), 2)
                        
                        processed += 1
                        
                    except Exception as e:
                        failed += 1
                        logger.warning(f"[embed] Falha ao processar candidato: {e}")
                        continue
                
                logger.info(
                    f"[embed] Processamento concluído: "
                    f"processed={processed} failed={failed}"
                )

        transcript.analysis_data = analysis_data
        transcript.save()

        video.last_successful_step = "embedding"
        video.status = "selecting"
        video.current_step = "selecting"
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "selecting",
            progress=60,
            current_step="selecting"
        )

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
        logger.error(f"[embed] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[embed] Error for video_id={video_id}: {e}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.error_message = str(e)[:500]
            video.save()

            _safe_update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="embedding"
            )

        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(
                f"[embed] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                f"in {countdown}s"
            )
            raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e)[:500], "status": "failed"}


def _get_batch_embeddings(
    client,
    texts: List[str],
    organization_id: str = ""
) -> List[Optional[List[float]]]:
    
    if not texts:
        return []

    output_dim = _get_config(
        "GEMINI_EMBED_OUTPUT_DIMENSIONALITY",
        DEFAULT_OUTPUT_DIMENSIONALITY,
        int
    )

    final_embeddings: List[Optional[List[float]]] = [None] * len(texts)
    
    texts_to_process: List[str] = []
    indices_to_process: List[int] = []
    
    for idx, text in enumerate(texts):
        if not text or not isinstance(text, str):
            logger.warning(f"[embed] Texto inválido no índice {idx}, pulando")
            continue
            
        cached = EmbeddingCacheService.get_embedding(text)
        if cached:
            final_embeddings[idx] = cached
            continue
        
        lock_acquired = EmbeddingCacheService.try_acquire_lock(text)
        
        if not lock_acquired:
            waited = EmbeddingCacheService.wait_for_embedding(
                text,
                attempts=10,
                sleep_seconds=0.25
            )
            
            if waited:
                final_embeddings[idx] = waited
                continue
            
            lock_acquired = EmbeddingCacheService.try_acquire_lock(text)
        
        if lock_acquired:
            texts_to_process.append(text)
            indices_to_process.append(idx)
        else:
            logger.warning(f"[embed] Não conseguiu lock para texto idx={idx}, processando sem cache")
            texts_to_process.append(text)
            indices_to_process.append(idx)
    
    if not texts_to_process:
        logger.info("[embed] Todos os embeddings vieram do cache")
        return final_embeddings
    
    logger.info(f"[embed] Processando {len(texts_to_process)} novos embeddings")
    
    batch_size = _get_config("GEMINI_EMBED_BATCH_SIZE", DEFAULT_BATCH_SIZE, int)
    batch_size = int(max(1, min(batch_size, 100)))

    total = len(texts_to_process)
    total_batches = (total + batch_size - 1) // batch_size

    processed_count = 0
    
    try:
        for batch_i in range(total_batches):
            start = batch_i * batch_size
            end = min(start + batch_size, total)
            
            batch_texts = texts_to_process[start:end]
            batch_indices = indices_to_process[start:end]

            logger.info(
                f"[embed] Batch {batch_i + 1}/{total_batches}: "
                f"processando {len(batch_texts)} textos"
            )

            try:
                enforce_gemini_rate_limit(organization_id=organization_id, kind="embed")

                response = client.models.embed_content(
                    model="text-embedding-004",
                    contents=batch_texts,
                    config=types.EmbedContentConfig(output_dimensionality=output_dim),
                )

                log_gemini_usage(
                    response,
                    organization_id=organization_id,
                    kind="embed",
                    model="text-embedding-004"
                )

                embedding_list = _extract_embedding_values(response)
                
                if len(embedding_list) != len(batch_texts):
                    raise RuntimeError(
                        f"Batch {batch_i + 1}: expected {len(batch_texts)} embeddings, "
                        f"got {len(embedding_list)}"
                    )

                for i, vals in enumerate(embedding_list):
                    if not vals or not isinstance(vals, list):
                        logger.warning(f"[embed] Embedding vazio no índice {i}")
                        continue

                    normalized = _normalize_embedding(vals)
                    
                    if not normalized or len(normalized) != output_dim:
                        logger.warning(
                            f"[embed] Normalização falhou ou dimensão incorreta: "
                            f"expected {output_dim}, got {len(normalized) if normalized else 0}"
                        )
                        continue

                    original_idx = batch_indices[i]
                    final_embeddings[original_idx] = normalized

                    try:
                        EmbeddingCacheService.save_embedding(batch_texts[i], normalized)
                        EmbeddingCacheService.release_lock(batch_texts[i])
                    except Exception as cache_err:
                        logger.warning(f"[embed] Cache save failed: {cache_err}")
                
                processed_count += len(batch_texts)
                
            except Exception as batch_err:
                logger.error(f"[embed] Batch {batch_i + 1} failed: {batch_err}")
                
                for i in range(len(batch_texts)):
                    try:
                        EmbeddingCacheService.release_lock(batch_texts[i])
                    except Exception:
                        pass
                
                raise
        
        logger.info(f"[embed] Processamento completo: {processed_count} embeddings")
        return final_embeddings

    except Exception as e:
        logger.error(f"[embed] Erro na API Gemini Embedding: {e}")
        
        for text in texts_to_process:
            try:
                EmbeddingCacheService.release_lock(text)
            except Exception:
                pass
        
        raise


def _extract_embedding_values(response) -> List[List[float]]:
    
    try:
        if isinstance(response, dict):
            embeddings = response.get("embeddings") or response.get("embedding")
        else:
            embeddings = getattr(response, "embeddings", None)
            if embeddings is None:
                embeddings = getattr(response, "embedding", None)

        if embeddings is None:
            logger.warning("[embed] No embeddings found in response")
            return []

        if not isinstance(embeddings, list):
            embeddings = [embeddings]

        result: List[List[float]] = []
        
        for emb_obj in embeddings:
            vals = None
            
            if isinstance(emb_obj, dict):
                vals = emb_obj.get("values") or emb_obj.get("value")
            else:
                vals = getattr(emb_obj, "values", None)
                if vals is None:
                    vals = getattr(emb_obj, "value", None)
            
            if vals is None:
                logger.warning("[embed] Embedding object has no values")
                result.append([])
                continue
            
            if not isinstance(vals, list):
                try:
                    vals = list(vals)
                except Exception:
                    logger.warning("[embed] Could not convert values to list")
                    result.append([])
                    continue
            
            result.append(vals)
        
        return result
        
    except Exception as e:
        logger.error(f"[embed] Error extracting embedding values: {e}")
        return []


def _normalize_embedding(embedding: List[float]) -> Optional[List[float]]:
    
    if not embedding or not isinstance(embedding, list):
        return None
    
    try:
        embedding_np = np.array(embedding, dtype=np.float32)
        
        if embedding_np.size == 0:
            return None
        
        embedding_norm = norm(embedding_np)
        
        if embedding_norm == 0 or np.isnan(embedding_norm) or np.isinf(embedding_norm):
            logger.warning("[embed] Embedding has zero/invalid norm")
            return None
        
        normalized = (embedding_np / embedding_norm).tolist()
        
        return normalized
        
    except Exception as e:
        logger.error(f"[embed] Normalization error: {e}")
        return None


def _get_reference_patterns(organization_id: str) -> List[np.ndarray]:
    
    try:
        from ..models import EmbeddingPattern
        
        max_patterns = _get_config("EMBEDDING_MAX_PATTERNS", 10, int)
        
        patterns = list(
            EmbeddingPattern.objects.filter(
                organization_id=organization_id
            ).values_list('embedding', flat=True)[:max_patterns]
        )
        
        if not patterns:
            logger.info(f"[embed] No patterns for org {organization_id}, using default")
            return [_get_default_viral_embedding()]
        
        parsed_patterns: List[List[float]] = []
        
        for p in patterns:
            try:
                if isinstance(p, str):
                    parsed = json.loads(p)
                    if isinstance(parsed, list):
                        parsed_patterns.append(parsed)
                elif isinstance(p, list):
                    parsed_patterns.append(p)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"[embed] Failed to parse pattern: {e}")
                continue
        
        if not parsed_patterns:
            logger.warning("[embed] No valid patterns parsed, using default")
            return [_get_default_viral_embedding()]
        
        normalized_patterns: List[np.ndarray] = []
        
        for pattern_list in parsed_patterns:
            try:
                pattern_np = np.array(pattern_list, dtype=np.float32)
                pattern_norm = norm(pattern_np)
                
                if pattern_norm == 0 or np.isnan(pattern_norm):
                    logger.warning("[embed] Pattern has zero/invalid norm, skipping")
                    continue
                
                normalized = pattern_np / pattern_norm
                normalized_patterns.append(normalized)
                
            except Exception as e:
                logger.warning(f"[embed] Failed to normalize pattern: {e}")
                continue
        
        if not normalized_patterns:
            logger.warning("[embed] No patterns normalized successfully, using default")
            return [_get_default_viral_embedding()]
        
        logger.info(f"[embed] Loaded {len(normalized_patterns)} reference patterns")
        return normalized_patterns
        
    except Exception as e:
        logger.error(f"[embed] Error loading patterns: {e}", exc_info=True)
        return [_get_default_viral_embedding()]


def _get_default_viral_embedding() -> np.ndarray:
    
    global _DEFAULT_VIRAL_EMBEDDING
    
    if _DEFAULT_VIRAL_EMBEDDING is not None:
        return _DEFAULT_VIRAL_EMBEDDING
    
    viral_concept = _get_config(
        "EMBEDDING_VIRAL_CONCEPT",
        DEFAULT_VIRAL_CONCEPT,
        str
    )
    
    try:
        client = get_gemini_client()
        
        embeds = _get_batch_embeddings(
            client,
            [viral_concept],
            organization_id="__global__"
        )
        
        if embeds and embeds[0]:
            embedding_np = np.array(embeds[0], dtype=np.float32)
            
            if norm(embedding_np) > 0:
                _DEFAULT_VIRAL_EMBEDDING = embedding_np
                logger.info("[embed] Default viral embedding generated successfully")
                return _DEFAULT_VIRAL_EMBEDDING
        
        logger.warning("[embed] Failed to generate viral embedding, using random")
        
    except Exception as e:
        logger.error(f"[embed] Error generating default viral embedding: {e}")
    
    output_dim = _get_config(
        "GEMINI_EMBED_OUTPUT_DIMENSIONALITY",
        DEFAULT_OUTPUT_DIMENSIONALITY,
        int
    )
    
    random_embedding = np.random.randn(output_dim).astype(np.float32)
    random_norm = norm(random_embedding)
    
    if random_norm > 0:
        random_embedding = random_embedding / random_norm
    
    _DEFAULT_VIRAL_EMBEDDING = random_embedding
    
    return _DEFAULT_VIRAL_EMBEDDING


def _calculate_similarity(
    embedding: List[float],
    reference_patterns: List[np.ndarray]
) -> float:
    
    if not embedding or not isinstance(embedding, list):
        logger.warning("[embed] Invalid embedding for similarity calculation")
        return DEFAULT_FALLBACK_SIMILARITY
    
    if not reference_patterns:
        logger.warning("[embed] No reference patterns for similarity calculation")
        return DEFAULT_FALLBACK_SIMILARITY

    try:
        embedding_np = np.array(embedding, dtype=np.float32)
        
        if embedding_np.size == 0:
            return DEFAULT_FALLBACK_SIMILARITY
        
        similarities: List[float] = []
        
        for pattern in reference_patterns:
            if not isinstance(pattern, np.ndarray):
                continue
            
            try:
                similarity = float(np.dot(embedding_np, pattern))
                
                if not np.isnan(similarity) and not np.isinf(similarity):
                    similarities.append(similarity)
                    
            except Exception as e:
                logger.warning(f"[embed] Similarity calculation failed for pattern: {e}")
                continue
        
        if not similarities:
            logger.warning("[embed] No valid similarities calculated")
            return DEFAULT_FALLBACK_SIMILARITY
        
        mean_similarity = float(np.mean(similarities))
        
        normalized = (mean_similarity + 1.0) / 2.0
        
        clamped = float(np.clip(normalized, 0.0, 1.0))
        
        return clamped
        
    except Exception as e:
        logger.error(f"[embed] Error calculating similarity: {e}")
        return DEFAULT_FALLBACK_SIMILARITY


def _adjust_score(
    engagement_score: float,
    similarity_score: float
) -> float:
    
    engagement_weight = _get_config(
        "EMBEDDING_ENGAGEMENT_WEIGHT",
        DEFAULT_ENGAGEMENT_WEIGHT,
        float
    )
    similarity_weight = _get_config(
        "EMBEDDING_SIMILARITY_WEIGHT",
        DEFAULT_SIMILARITY_WEIGHT,
        float
    )
    
    engagement_weight = float(max(0.0, min(engagement_weight, 1.0)))
    similarity_weight = float(max(0.0, min(similarity_weight, 1.0)))
    
    total_weight = engagement_weight + similarity_weight
    if total_weight <= 0:
        total_weight = 1.0
    
    engagement_weight = engagement_weight / total_weight
    similarity_weight = similarity_weight / total_weight
    
    try:
        eng_score = float(max(0.0, min(engagement_score, 100.0)))
        sim_score = float(max(0.0, min(similarity_score, 1.0)))
        
        adjusted = (eng_score * engagement_weight) + (sim_score * 100.0 * similarity_weight)
        
        clamped = float(np.clip(adjusted, 0.0, 100.0))
        
        return clamped
        
    except Exception as e:
        logger.error(f"[embed] Error adjusting score: {e}")
        return float(engagement_score)