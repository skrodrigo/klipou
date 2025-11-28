from typing import Any, Dict

from ..models import VideoClip


def create_video_clip(title: str) -> Dict[str, Any]:
    clip = VideoClip.objects.create(title=title)
    return {
        "id": clip.id,
        "title": clip.title,
        "created_at": clip.created_at,
    }
