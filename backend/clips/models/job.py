"""
Model para rastreamento de jobs de processamento de vídeo.
"""

import uuid
from django.db import models


class Job(models.Model):
    STATUS_CHOICES = [
        ("ingestion", "Ingestion"),
        ("queued", "Queued"),
        ("downloading", "Downloading"),
        ("normalizing", "Normalizing"),
        ("transcribing", "Transcribing"),
        ("analyzing", "Analyzing"),
        ("embedding", "Embedding"),
        ("selecting", "Selecting"),
        ("reframing", "Reframing"),
        ("clipping", "Clipping"),
        ("captioning", "Captioning"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    # Identificadores
    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()  # FK para User (futuro)
    organization_id = models.UUIDField()  # FK para Organization
    video_id = models.UUIDField()  # FK para Video

    # Status e progresso
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ingestion")
    current_step = models.CharField(max_length=50, null=True, blank=True)
    last_successful_step = models.CharField(max_length=50, null=True, blank=True)
    progress = models.IntegerField(default=0)  # 0-100

    # Configuração do job
    configuration = models.JSONField(default=dict)  # language, target_ratios, max_clip_duration, num_clips, etc

    # Erros
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Créditos
    credits_consumed = models.IntegerField(default=0)

    # Retry
    retry_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Versionamento e soft delete
    version = models.IntegerField(default=1)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["job_id"]),
            models.Index(fields=["user_id"]),
        ]

    def __str__(self) -> str:
        return f"Job {self.job_id} - {self.status}"
