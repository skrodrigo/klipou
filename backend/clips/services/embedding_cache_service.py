import hashlib
import logging
from django.core.cache import cache
from ..models import EmbeddingCache

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 30

LOCK_TTL_SECONDS = 60 * 5


class EmbeddingCacheService:
    @staticmethod
    def get_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def get_embedding(text: str) -> list | None:
        text_hash = EmbeddingCacheService.get_hash(text)
        
        cached = cache.get(f"embedding:{text_hash}")
        if cached:
            return cached
        
        try:
            cache_obj = EmbeddingCache.objects.get(text_hash=text_hash)
            cache_obj.access_count += 1
            cache_obj.save(update_fields=['access_count', 'last_accessed'])
            
            cache.set(f"embedding:{text_hash}", cache_obj.embedding, CACHE_TTL)
            return cache_obj.embedding
        except EmbeddingCache.DoesNotExist:
            return None
        except Exception as e:
            logger.warning(f"Erro ao recuperar embedding do cache: {e}")
            return None

    @staticmethod
    def _lock_key(text_hash: str) -> str:
        return f"embedding_lock:{text_hash}"

    @staticmethod
    def try_acquire_lock(text: str, ttl_seconds: int = LOCK_TTL_SECONDS) -> bool:
        text_hash = EmbeddingCacheService.get_hash(text)
        # cache.add is atomic for Redis backends.
        try:
            return bool(cache.add(EmbeddingCacheService._lock_key(text_hash), 1, timeout=int(ttl_seconds)))
        except Exception:
            return True

    @staticmethod
    def release_lock(text: str) -> None:
        text_hash = EmbeddingCacheService.get_hash(text)
        try:
            cache.delete(EmbeddingCacheService._lock_key(text_hash))
        except Exception:
            return

    @staticmethod
    def wait_for_embedding(text: str, *, attempts: int = 8, sleep_seconds: float = 0.25) -> list | None:
        # Best-effort polling; used when another worker is computing the embedding.
        import time

        for _ in range(int(max(1, attempts))):
            emb = EmbeddingCacheService.get_embedding(text)
            if emb:
                return emb
            time.sleep(float(max(0.05, sleep_seconds)))
        return None

    @staticmethod
    def save_embedding(text: str, embedding: list) -> EmbeddingCache:
        text_hash = EmbeddingCacheService.get_hash(text)
        
        cache_obj, created = EmbeddingCache.objects.update_or_create(
            text_hash=text_hash,
            defaults={
                'text_content': text,
                'embedding': embedding,
            }
        )
        
        cache.set(f"embedding:{text_hash}", embedding, CACHE_TTL)
        return cache_obj
