from django.db import models
import uuid


class Video(models.Model):
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
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("upload", "Upload"),
        ("youtube", "YouTube"),
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("url", "URL"),
    ]

    # Identificadores
    video_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization_id = models.UUIDField(null=True, blank=True)  # FK para Organization (futuro)
    user_id = models.UUIDField(null=True, blank=True)  # FK para User (futuro)

    # Metadados
    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default="upload")
    source_url = models.URLField(null=True, blank=True)
    original_filename = models.CharField(max_length=500, null=True, blank=True)

    # Armazenamento
    file = models.FileField(upload_to="videos/", blank=True, null=True, max_length=500)  # Local (deprecated)
    storage_path = models.CharField(max_length=500, null=True, blank=True)  # Caminho no R2
    file_size = models.BigIntegerField(null=True, blank=True)  # Tamanho em bytes

    # Processamento
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ingestion")
    duration = models.FloatField(null=True, blank=True)  # Duração em segundos
    resolution = models.CharField(max_length=20, null=True, blank=True)  # Ex: 1920x1080
    thumbnail = models.TextField(null=True, blank=True)  # Base64 ou URL do R2
    thumbnail_storage_path = models.CharField(max_length=500, null=True, blank=True)  # Caminho no R2

    # Job tracking
    task_id = models.CharField(max_length=255, blank=True, null=True)
    current_step = models.CharField(max_length=50, null=True, blank=True)
    last_successful_step = models.CharField(max_length=50, null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Versionamento
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["video_id"]),
        ]

    def __str__(self) -> str:
        return self.title
