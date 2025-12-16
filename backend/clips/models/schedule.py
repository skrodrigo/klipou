"""
Model para agendamento de posts em redes sociais.
"""

import uuid
from django.db import models
from .clip import Clip


class Schedule(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("posted", "Posted"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
    ]

    PLATFORM_CHOICES = [
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("youtube", "YouTube"),
        ("linkedin", "LinkedIn"),
        ("twitter", "X (Twitter)"),
    ]

    # Identificadores
    schedule_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE, related_name="schedules")
    user_id = models.UUIDField()  # FK para User

    # Plataforma
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    # Agendamento
    scheduled_time = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    post_url = models.URLField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["platform"]),
        ]

    def __str__(self) -> str:
        return f"{self.clip.title} - {self.platform} ({self.status})"
