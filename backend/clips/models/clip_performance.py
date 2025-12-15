"""
Model para performance de clips em redes sociais.
"""

import uuid
from django.db import models


class ClipPerformance(models.Model):
    PLATFORM_CHOICES = [
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("facebook", "Facebook"),
        ("linkedin", "LinkedIn"),
        ("twitter", "Twitter"),
    ]

    # Identificadores
    performance_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    clip_id = models.UUIDField()  # FK para Clip

    # Plataforma
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    post_url = models.URLField()

    # Métricas
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    engagement_rate = models.FloatField(default=0.0)

    # Timestamps
    collected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-collected_at"]
        indexes = [
            models.Index(fields=["clip_id", "platform"]),
            models.Index(fields=["platform", "updated_at"]),
        ]
        unique_together = [["clip_id", "platform"]]

    def __str__(self) -> str:
        return f"{self.clip_id} - {self.platform}"
