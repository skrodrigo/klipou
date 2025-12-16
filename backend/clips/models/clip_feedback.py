"""
Model para feedback de clips.
"""

import uuid
from django.db import models
from .clip import Clip


class ClipFeedback(models.Model):
    RATING_CHOICES = [
        ("good", "Good"),
        ("bad", "Bad"),
    ]

    # Identificadores
    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE, related_name="feedbacks")
    user_id = models.UUIDField()  # FK para User

    # Feedback
    rating = models.CharField(max_length=10, choices=RATING_CHOICES)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clip_id", "user_id"]),
            models.Index(fields=["rating"]),
        ]
        unique_together = [["clip", "user_id"]]

    def __str__(self) -> str:
        return f"{self.clip.title} - {self.rating}"
