"""
Model para integrações com redes sociais.
"""

import uuid
from django.db import models
from .organization import Organization


class Integration(models.Model):
    PLATFORM_CHOICES = [
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("youtube", "YouTube"),
        ("linkedin", "LinkedIn"),
        ("twitter", "X (Twitter)"),
    ]

    # Identificadores
    integration_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="integrations")

    # Plataforma
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    account_name = models.CharField(max_length=255)

    # Token (criptografado)
    token_encrypted = models.TextField()  # Deve ser criptografado em produção
    token_refresh_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "platform"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["organization", "platform", "account_name"]]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.platform} (@{self.account_name})"
