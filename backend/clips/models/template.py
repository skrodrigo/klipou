"""
Model para templates visuais de clips.
"""

import uuid
from django.db import models


class Template(models.Model):
    TYPE_CHOICES = [
        ("overlay", "Overlay"),
        ("bar", "Bar"),
        ("effect", "Effect"),
        ("text_style", "Text Style"),
    ]

    # Identificadores
    template_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Configuração
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    ffmpeg_filter = models.TextField()  # Comando FFmpeg
    preview_url = models.URLField(blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Versionamento
    version = models.IntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["type", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.type})"
