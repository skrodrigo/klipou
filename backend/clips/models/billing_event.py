"""
Model para eventos de billing e assinatura.
"""

import uuid
from django.db import models


class BillingEvent(models.Model):
    EVENT_CHOICES = [
        ("upgrade", "Upgrade"),
        ("downgrade", "Downgrade"),
        ("renewal", "Renewal"),
        ("payment_failed", "Payment Failed"),
        ("payment_succeeded", "Payment Succeeded"),
        ("subscription_created", "Subscription Created"),
        ("subscription_canceled", "Subscription Canceled"),
    ]

    # Identificadores
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.UUIDField()  # FK para Organization

    # Evento
    type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    old_plan = models.CharField(max_length=20, blank=True, null=True)
    new_plan = models.CharField(max_length=20, blank=True, null=True)

    # Valores
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Stripe
    stripe_event_id = models.CharField(max_length=255, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.type} - {self.organization_id}"
