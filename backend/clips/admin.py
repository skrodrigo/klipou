from django.contrib import admin

from .models import Video, Clip


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at")
    ordering = ("-created_at",)


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at", "video_id")
    ordering = ("-created_at",)
