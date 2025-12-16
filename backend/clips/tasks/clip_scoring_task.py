import logging
import os
import cv2
from celery import shared_task
from django.conf import settings

from ..models import Clip, Video, Transcript
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def clip_scoring_task(self, clip_id: str, video_id: str):
    local_clip_path = None
    thumb_path = None

    try:
        logger.info(f"Iniciando post-processing para clip_id={clip_id}")
        
        clip = Clip.objects.get(clip_id=clip_id)
        video = Video.objects.get(video_id=video_id)
        transcript = Transcript.objects.filter(video=video).first()
        
        matched_data = None
        
        if transcript and transcript.selected_clips:
            for candidate in transcript.selected_clips:
                if abs(candidate.get("start_time", 0) - clip.start_time) < 0.5:
                    matched_data = candidate
                    break
        
        if matched_data:
            clip.engagement_score = int(matched_data.get("score", 0))
            clip.title = matched_data.get("title") or clip.title
            logger.info(f"Scores recuperados da IA: {clip.engagement_score}")
        else:
            logger.warning("Dados de IA não encontrados para este clip. Usando fallback.")
            clip.engagement_score = 70

        storage = R2StorageService()
        
        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_thumbs")
        os.makedirs(temp_dir, exist_ok=True)
        
        local_clip_path = os.path.join(temp_dir, f"{clip_id}.mp4")
        
        if clip.storage_path:
            storage.download_file(clip.storage_path, local_clip_path)
        
        if os.path.exists(local_clip_path):
            thumb_path = _extract_vertical_thumbnail(local_clip_path, temp_dir, clip_id)
            
            if thumb_path:
                thumb_storage_path = storage.upload_thumbnail(
                    file_path=thumb_path, 
                    organization_id=str(video.organization_id), 
                    video_id=str(video_id),
                    filename=f"thumb_{clip_id}.jpg"
                )
                clip.thumbnail_storage_path = thumb_storage_path
                logger.info(f"Thumbnail gerada: {thumb_storage_path}")

        clip.save()
        
        return {
            "clip_id": str(clip_id),
            "score": clip.engagement_score,
            "has_thumbnail": bool(clip.thumbnail_storage_path)
        }
    
    except Exception as e:
        logger.error(f"Erro no scoring/thumb do clip {clip_id}: {str(e)}", exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return {"error": str(e)}
        
    finally:
        if local_clip_path and os.path.exists(local_clip_path):
            try:
                os.remove(local_clip_path)
            except:
                pass
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except:
                pass


def _extract_vertical_thumbnail(video_path: str, output_dir: str, clip_id: str) -> str:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    target_frame = int(total_frames * 0.20)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return None
        
    output_path = os.path.join(output_dir, f"{clip_id}_thumb.jpg")
    cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    
    return output_path
