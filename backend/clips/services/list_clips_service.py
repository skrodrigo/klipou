from typing import Any, Dict, List

from ..models import VideoClip


def list_video_clips() -> List[Dict[str, Any]]:
    return list(
        VideoClip.objects.order_by("-created_at").values("id", "title", "created_at")
    )
