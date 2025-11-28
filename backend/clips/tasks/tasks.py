from __future__ import annotations

from ..models import VideoClip


def process_clip_task(clip_id: int) -> str:
    try:
        clip = VideoClip.objects.get(id=clip_id)
    except VideoClip.DoesNotExist:
        return f"Clip {clip_id} not found"

    return f"Processed clip {clip.id}"
