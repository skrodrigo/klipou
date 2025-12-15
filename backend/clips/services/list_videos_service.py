from typing import Any, Dict, List

from ..models import Video
from .storage_service import R2StorageService


def list_videos() -> List[Dict[str, Any]]:
    """
    Lista todos os vídeos ordenados por data de criação (mais recentes primeiro).
    Retorna URLs assinadas para thumbnails e clips.
    
    Returns:
        Lista de dicts com id, title, created_at, status, progress, clips
    """
    from django.core.cache import cache
    
    storage = R2StorageService()
    videos = []
    
    for video in Video.objects.prefetch_related("clips").order_by("-created_at"):
        status_data = cache.get(f"video_status_{video.id}")
        progress = status_data.get("progress", 0) if status_data else 0
        
        # Gera URL assinada para thumbnail
        thumbnail_url = video.thumbnail
        if video.thumbnail_storage_path:
            try:
                thumbnail_url = storage.get_signed_url(video.thumbnail_storage_path, expiration=86400)
            except Exception:
                thumbnail_url = video.thumbnail  # Fallback para base64 ou URL anterior
        
        clips = []
        for clip in video.clips.all():
            clip_data = {
                "id": clip.id,
                "clip_id": str(clip.clip_id),
                "title": clip.title,
                "created_at": clip.created_at.isoformat(),
                "video_id": clip.video_id,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "duration": clip.duration,
                "engagement_score": clip.engagement_score,
            }
            
            # Gera URL assinada para clip
            if clip.storage_path:
                try:
                    clip_data["storage_url"] = storage.get_signed_url(clip.storage_path, expiration=3600)
                except Exception:
                    pass
            
            clips.append(clip_data)
        
        videos.append({
            "id": video.id,
            "video_id": str(video.video_id),
            "title": video.title,
            "created_at": video.created_at.isoformat(),
            "status": video.status,
            "progress": progress,
            "duration": video.duration,
            "thumbnail": thumbnail_url,
            "storage_path": video.storage_path,
            "clips": clips,
        })
    return videos
