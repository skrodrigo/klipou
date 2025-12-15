"""
Model para assinaturas/planos.
"""

import uuid
from django.db import models
from .organization import Organization


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
    ]

    # Identificadores
    subscription_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="subscription")

    # Stripe
    stripe_subscription_id = models.CharField(max_length=255, unique=True)

    # Plano
    plan = models.CharField(max_length=20, choices=[
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("business", "Business"),
    ])

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Período
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.plan}"
