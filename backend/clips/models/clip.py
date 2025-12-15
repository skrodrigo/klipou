from django.db import models
import uuid
from .job import Job
from .video import Video


class Clip(models.Model):
    # Identificadores
    clip_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="clips", null=True, blank=True)
    
    video = models.ForeignKey(
        Video,
        related_name="clips",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    # Metadados
    title = models.CharField(max_length=255)
    start_time = models.FloatField(default=0)  # Em segundos
    end_time = models.FloatField(default=0)  # Em segundos
    duration = models.FloatField(null=True, blank=True)  # Em segundos (calculado)
    ratio = models.CharField(max_length=10, null=True, blank=True)  # Ex: 9:16, 1:1, 16:9

    # Armazenamento
    storage_path = models.CharField(max_length=500, null=True, blank=True)  # Caminho no R2
    file_size = models.BigIntegerField(null=True, blank=True)  # Tamanho em bytes

    # Scoring e análise
    engagement_score = models.IntegerField(null=True, blank=True)  # 0-100
    confidence_score = models.IntegerField(null=True, blank=True)  # 0-100

    # Versionamento
    version = models.IntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["video_id", "-created_at"]),
            models.Index(fields=["clip_id"]),
            models.Index(fields=["engagement_score"]),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return self.title
