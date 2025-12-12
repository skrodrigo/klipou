from django.db import models


class Video(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="videos/", blank=True, null=True, max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    duration = models.FloatField(null=True, blank=True)
    thumbnail = models.TextField(null=True, blank=True)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title
