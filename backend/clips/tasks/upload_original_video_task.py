import logging
import os

from celery import shared_task
from django.conf import settings

from ..models import Video
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, acks_late=False)
def upload_original_video_task(self, video_id: str) -> dict:
    video = None
    try:
        video = Video.objects.get(video_id=video_id)

        if video.storage_path:
            return {"video_id": str(video.video_id), "status": "skipped", "detail": "already_uploaded"}

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video.video_id}")
        local_video_path = os.path.join(output_dir, "video_original.mp4")

        if not os.path.exists(local_video_path):
            raise FileNotFoundError(f"Arquivo original não encontrado: {local_video_path}")

        storage = R2StorageService()
        uploaded_key = storage.upload_video(
            file_path=local_video_path,
            organization_id=str(video.organization_id),
            video_id=str(video.video_id),
            original_filename=video.original_filename or "video_original.mp4",
        )

        video.storage_path = uploaded_key
        video.save(update_fields=["storage_path"])

        logger.info("Upload async do vídeo original para R2 concluído: video_id=%s key=%s", str(video.video_id), uploaded_key)

        return {"video_id": str(video.video_id), "status": "uploaded", "storage_path": uploaded_key}

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error("Erro no upload async do original %s: %s", video_id, e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        if video:
            try:
                video.error_message = str(e)
                video.save(update_fields=["error_message"])
            except Exception:
                pass
        return {"error": str(e), "status": "failed"}
