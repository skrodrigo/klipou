from typing import Any, Dict, List

from ..models import Clip


def list_video_clips(video_id: int) -> List[Dict[str, Any]]:
    """
    Lista todos os clips de um vídeo específico.
    
    Args:
        video_id: ID do vídeo
        
    Returns:
        Lista de dicts com id, title, created_at, video_id
    """
    clips_qs = Clip.objects.filter(video_id=video_id).order_by("-created_at")
    return [
        {
            "id": clip.id,
            "title": clip.title,
            "created_at": clip.created_at.isoformat(),
            "video_id": clip.video_id,
        }
        for clip in clips_qs
    ]
