"""
Model para membros de equipe em uma organização.
"""

import uuid
from django.db import models


class TeamMember(models.Model):
    ROLE_CHOICES = [
        ("member", "Member"),
        ("co-leader", "Co-leader"),
        ("leader", "Leader"),
    ]

    # Identificadores
    member_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.UUIDField()  # FK para Organization
    user_id = models.UUIDField()  # FK para User

    # Papel na organização
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-joined_at"]
        indexes = [
            models.Index(fields=["organization_id", "user_id"]),
            models.Index(fields=["organization_id", "role"]),
        ]
        unique_together = [["organization_id", "user_id"]]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.role} in {self.organization_id}"
