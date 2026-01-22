import uuid
from django.db import models
from django.conf import settings
from .organization import Organization

class OrganizationMember(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    membership_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'organization')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} - {self.organization.name} ({self.role})'
