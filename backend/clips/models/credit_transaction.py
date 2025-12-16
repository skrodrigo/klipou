"""
Model para transações de crédito.
"""

import uuid
from django.db import models
from .organization import Organization


class CreditTransaction(models.Model):
    TYPE_CHOICES = [
        ("consumption", "Consumption"),
        ("refund", "Refund"),
        ("purchase", "Purchase"),
        ("monthly_renewal", "Monthly Renewal"),
        ("adjustment", "Adjustment"),
    ]

    # Identificadores
    transaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.UUIDField(null=True, blank=True)  # FK para Organization
    job_id = models.UUIDField(null=True, blank=True)  # FK para Job (opcional)

    # Transação
    amount = models.IntegerField()  # Positivo = dedução, Negativo = estorno
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    reason = models.TextField()

    # Saldo
    balance_after = models.IntegerField()  # Saldo após transação

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "-created_at"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization_id} - {self.type} ({self.amount})"
