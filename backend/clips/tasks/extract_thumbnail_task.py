import logging
import cv2
import os
import glob
import subprocess
from celery import shared_task
from ..models import Video, Organization
from ..services.storage_service import R2StorageService
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, acks_late=False)
def extract_thumbnail_task(self, video_id: str):
    video = None
    cap = None
    thumbnail_path = None
    
    try:
        logger.info(f"Iniciando extração de thumbnail para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        
        video.current_step = "extracting_thumbnail"
        video.save()
        update_job_status(str(video_id), "normalizing", progress=15, current_step="extracting_thumbnail")
        
        from django.conf import settings
        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        video_path = None

        potential_path = os.path.join(video_dir, "video_original.mp4")
        if os.path.exists(potential_path):
            video_path = potential_path
        else:
            search_patterns = ['*.mp4', '*.mkv', '*.mov', '*.webm']
            for pattern in search_patterns:
                files = glob.glob(os.path.join(video_dir, pattern))
                if files:
                    video_path = files[0]
                    break
        
        if not video_path and video.file and os.path.exists(video.file.path):
            video_path = video.file.path

        if not video_path:
            raise Exception(f"Arquivo de vídeo não encontrado em {video_dir}")

        logger.info(f"Arquivo de vídeo localizado: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise Exception(f"Não foi possível abrir o arquivo de vídeo: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames <= 0:
            raise Exception("Vídeo não possui frames ou está corrompido")
        
        target_frame = int(total_frames * 0.25)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        ret, frame = cap.read()

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 1)
            ret, frame = cap.read()

        if not ret:
            thumbnail_dir = os.path.join(video_dir, 'thumbnails')
            os.makedirs(thumbnail_dir, exist_ok=True)
            thumbnail_path = os.path.join(thumbnail_dir, f"{video_id}_thumb.jpg")

            ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
            ts = max(float(video.duration or 0) * 0.25, 1.0)
            cmd = [
                ffmpeg_path,
                "-ss", str(ts),
                "-i", video_path,
                "-frames:v", "1",
                "-vf", "scale=320:-1",
                "-q:v", "4",
                "-y",
                thumbnail_path,
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.info(f"Fazendo upload da thumbnail para R2...")
            storage = R2StorageService()
            r2_thumbnail_path = storage.upload_thumbnail(thumbnail_path, video.organization_id, video_id)

            video.thumbnail_storage_path = r2_thumbnail_path
            video.last_successful_step = "extracting_thumbnail"
            video.status = "normalizing"
            video.current_step = "normalizing"
            video.save()

            logger.info(f"Thumbnail salva com sucesso: {r2_thumbnail_path}")
            update_job_status(str(video_id), "normalizing", progress=20, current_step="normalizing")

            org = Organization.objects.get(organization_id=video.organization_id)

            from .normalize_video_task import normalize_video_task
            normalize_video_task.apply_async(
                args=[str(video_id)],
                queue=f"video.normalize.{get_plan_tier(org.plan)}",
            )

            return str(video_id)

        original_height, original_width = frame.shape[:2]
        max_dim = 320
        
        ratio = min(max_dim / original_width, max_dim / original_height)
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)
        
        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        thumbnail_dir = os.path.join(video_dir, 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_path = os.path.join(thumbnail_dir, f"{video_id}_thumb.jpg")
        
        cv2.imwrite(thumbnail_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        
        logger.info(f"Fazendo upload da thumbnail para R2...")
        storage = R2StorageService()
        r2_thumbnail_path = storage.upload_thumbnail(thumbnail_path, video.organization_id, video_id)
        
        video.thumbnail_storage_path = r2_thumbnail_path
        video.last_successful_step = "extracting_thumbnail"
        video.status = "normalizing"
        video.current_step = "normalizing"
        video.save()
        
        logger.info(f"Thumbnail salva com sucesso: {r2_thumbnail_path}")
        
        update_job_status(str(video_id), "normalizing", progress=20, current_step="normalizing")
        
        org = Organization.objects.get(organization_id=video.organization_id)
        
        from .normalize_video_task import normalize_video_task
        normalize_video_task.apply_async(
            args=[str(video_id)],
            queue=f"video.normalize.{get_plan_tier(org.plan)}",
        )
        
        return str(video_id)

    except Video.DoesNotExist:
        logger.error(f"Vídeo {video_id} não encontrado no banco")
        return {"error": "Video not found"}
        
    except Exception as e:
        logger.error(f"Erro ao extrair thumbnail: {str(e)}", exc_info=True)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        else:
            if video:
                update_job_status(str(video_id), "failed", progress=100, current_step="extracting_thumbnail")
            raise e
            
    finally:
        if cap:
            cap.release()
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except OSError:
                pass
