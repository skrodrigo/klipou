import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField


class EmbeddingPattern(models.Model):
    CATEGORY_CHOICES = [
        ('engagement', 'High Engagement'),
        ('viral', 'Viral Content'),
        ('educational', 'Educational'),
        ('entertainment', 'Entertainment'),
    ]

    pattern_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='embedding_patterns')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    embedding = ArrayField(models.FloatField())
    embedding_dimension = models.IntegerField(default=768)
    embedding_model = models.CharField(default="gemini-embedding-004", max_length=100)
    description = models.TextField(blank=True)
    sample_count = models.IntegerField(default=0)
    confidence_score = models.FloatField(default=0.5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['organization', 'category']),
            models.Index(fields=['organization']),
        ]
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.category})"
