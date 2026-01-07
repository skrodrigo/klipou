from typing import Any, Dict, List

from ..models import Clip, Video
from .storage_service import R2StorageService


def list_video_clips(video_id: str) -> List[Dict[str, Any]]:
    clips_qs = Clip.objects.filter(video_id=video_id).select_related("video").order_by("-engagement_score", "-created_at")
    storage_service = R2StorageService()

    full_video_url = None
    try:
        video = Video.objects.get(video_id=video_id)
        if video.storage_path:
            try:
                full_video_url = storage_service.get_public_url(video.storage_path)
            except Exception:
                full_video_url = None
    except Video.DoesNotExist:
        full_video_url = None
    
    clips_data = []
    for clip in clips_qs:
        clip_dict = {
            "clip_id": str(clip.clip_id),
            "title": clip.title,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "duration": clip.duration,
            "ratio": clip.ratio,
            "engagement_score": clip.engagement_score,
            "confidence_score": clip.confidence_score,
            "created_at": clip.created_at.isoformat(),
            "updated_at": clip.updated_at.isoformat(),
            "full_video_url": full_video_url,
        }
        
        # Gera URL pública fixa para vídeo (exibição no frontend)
        if clip.storage_path:
            try:
                clip_dict["video_url"] = storage_service.get_public_url(clip.storage_path)
            except Exception:
                clip_dict["video_url"] = None
        else:
            clip_dict["video_url"] = None
        
        # Gera URL pública fixa para thumbnail (exibição no frontend)
        if clip.thumbnail_storage_path:
            try:
                clip_dict["thumbnail_url"] = storage_service.get_public_url(clip.thumbnail_storage_path)
            except Exception:
                clip_dict["thumbnail_url"] = None
        else:
            clip_dict["thumbnail_url"] = None
        
        # Obtém transcrição (campo de texto direto)
        clip_dict["transcript"] = clip.transcript if clip.transcript else None
        
        clips_data.append(clip_dict)
    
    return clips_data
