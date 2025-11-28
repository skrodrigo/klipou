from django.contrib import admin

from .models import Video, VideoClip


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at")
    ordering = ("-created_at",)


@admin.register(VideoClip)
class VideoClipAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at", "video_id")
    ordering = ("-created_at",)
