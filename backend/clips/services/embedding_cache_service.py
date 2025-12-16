import hashlib
import logging
from django.core.cache import cache
from ..models import EmbeddingCache

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 30


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
