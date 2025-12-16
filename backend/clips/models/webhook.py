"""
Model para webhooks customizados de organizações.
"""

import uuid
from django.db import models


class Webhook(models.Model):
    EVENT_CHOICES = [
        ("job_started", "Job Started"),
        ("job_completed", "Job Completed"),
        ("job_failed", "Job Failed"),
        ("clip_ready", "Clip Ready"),
        ("post_published", "Post Published"),
    ]

    # Identificadores
    webhook_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.UUIDField()  # FK para Organization

    # Configuração
    url = models.URLField()
    secret = models.CharField(max_length=255)  # Para validação HMAC
    events = models.JSONField(default=list)  # Lista de eventos

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Webhook {self.webhook_id} for {self.organization_id}"
