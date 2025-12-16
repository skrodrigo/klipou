import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField


class EmbeddingCache(models.Model):
    cache_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    text_hash = models.CharField(max_length=64, unique=True, db_index=True)
    text_content = models.TextField()
    embedding = ArrayField(models.FloatField())
    embedding_dimension = models.IntegerField(default=768)
    embedding_model = models.CharField(default="gemini-embedding-004", max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)
    access_count = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['text_hash']),
            models.Index(fields=['last_accessed']),
        ]

    def __str__(self):
        return f"Cache: {self.text_hash[:16]}..."
