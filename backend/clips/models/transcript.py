"""
Model para transcrições de vídeo.
"""

import uuid
from django.db import models
from .video import Video


class Transcript(models.Model):
    # Identificadores
    transcript_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="transcript")

    # Conteúdo
    full_text = models.TextField()  # Transcrição completa
    segments = models.JSONField(default=list)  # Array de segmentos com timestamps

    # Análise
    analysis_data = models.JSONField(default=dict, null=True, blank=True)  # Dados da análise Gemini
    selected_clips = models.JSONField(default=list, null=True, blank=True)  # Clips selecionados
    reframe_data = models.JSONField(default=dict, null=True, blank=True)  # Dados de reenquadramento
    caption_files = models.JSONField(default=list, null=True, blank=True)  # Arquivos ASS gerados

    # Metadados
    language = models.CharField(max_length=10, default="en")  # pt-BR, en, es, etc
    confidence_score = models.IntegerField(default=0)  # 0-100

    # Armazenamento
    storage_path = models.CharField(max_length=500, null=True, blank=True)  # Caminho no R2

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Versionamento
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["video_id"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self) -> str:
        return f"Transcript for {self.video.title}"
