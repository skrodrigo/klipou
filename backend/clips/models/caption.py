"""
Model para legendas de clips em formato ASS.
"""

import uuid
from django.db import models


class Caption(models.Model):
    STYLE_CHOICES = [
        ("bold", "Bold"),
        ("uppercase", "Uppercase"),
        ("centered", "Centered"),
        ("karaoke", "Karaoke"),
    ]

    # Identificadores
    caption_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clip_id = models.UUIDField()  # FK para Clip

    # Configuração
    format = models.CharField(max_length=10, default="ASS")
    content = models.TextField()  # Arquivo ASS em texto
    storage_path = models.CharField(max_length=255)  # Caminho no R2

    # Estilo
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default="centered")

    # Versionamento
    version = models.IntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clip_id"]),
        ]

    def __str__(self) -> str:
        return f"Caption {self.caption_id} for {self.clip_id}"
