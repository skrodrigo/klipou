"""
Model para segmentos de transcrição com suporte a multi-idioma.
"""

import uuid
from django.db import models


class TranscriptSegment(models.Model):
    # Identificadores
    segment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript_id = models.UUIDField()  # FK para Transcript

    # Conteúdo
    text = models.TextField()
    start_time = models.FloatField()  # em segundos
    end_time = models.FloatField()  # em segundos

    # Idioma
    language = models.CharField(
        max_length=10,
        choices=[
            ("pt-BR", "Português (Brasil)"),
            ("pt-PT", "Português (Portugal)"),
            ("en-US", "Inglês (US)"),
            ("en-GB", "Inglês (UK)"),
            ("es", "Espanhol"),
            ("fr", "Francês"),
            ("de", "Alemão"),
            ("it", "Italiano"),
            ("ja", "Japonês"),
            ("zh-CN", "Chinês (Simplificado)"),
            ("zh-TW", "Chinês (Tradicional)"),
            ("other", "Outro"),
        ],
        default="pt-BR"
    )

    # Confiança
    confidence = models.IntegerField(default=100)  # 0-100
    is_auto_detected = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["transcript_id", "start_time"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self) -> str:
        return f"{self.transcript_id} - {self.start_time}s - {self.language}"
