"""
Model para organizações.
Recursos pertencem à organização, não ao usuário.
"""

import uuid
from django.db import models


class Organization(models.Model):
    PLAN_CHOICES = [
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("business", "Business"),
    ]

    # Identificadores
    organization_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)

    # Plano
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")

    # Créditos
    credits_monthly = models.IntegerField(default=0)  # Créditos mensais renovável
    credits_available = models.IntegerField(default=0)  # Saldo atual
    credits_purchased = models.IntegerField(default=0)  # Acumulado comprado

    # Billing
    billing_email = models.EmailField()
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id"]),
            models.Index(fields=["plan"]),
        ]

    def __str__(self) -> str:
        return self.name
