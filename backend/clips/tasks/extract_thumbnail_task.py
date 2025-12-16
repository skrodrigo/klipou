"""
Task para extrair thumbnail do vídeo e salvar no R2.
"""

import cv2
import os
from celery import shared_task
from ..models import Video
from ..services.storage_service import R2StorageService
from .job_utils import update_job_status


@shared_task(bind=True, max_retries=3)
def extract_thumbnail_task(self, video_id: str):
    """
    Extrai thumbnail do vídeo em 25% do tempo total.
    Integrada na pipeline do Celery após download_video_task.
    
    Args:
        video_id: ID do vídeo (UUID)
    
    Returns:
        video_id para a próxima task na chain
    """
    try:
        video = Video.objects.get(video_id=video_id)
        
        print(f"[extract_thumbnail_task] Iniciando para video_id={video_id}")
        print(f"[extract_thumbnail_task] video.file={video.file}, video.storage_path={video.storage_path}")
        
        # Atualiza status
        video.current_step = "extracting_thumbnail"
        video.save()
        update_job_status(str(video_id), "extracting_thumbnail", progress=15, current_step="extracting_thumbnail")
        
        # Procura pelo arquivo local
        from django.conf import settings
        video_path = None
        
        # Tenta o caminho padrão de download
        default_path = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}/video_original.mp4")
        if os.path.exists(default_path):
            video_path = default_path
            print(f"[extract_thumbnail_task] Arquivo encontrado em: {video_path}")
        elif video.file and os.path.exists(video.file.path):
            video_path = video.file.path
            print(f"[extract_thumbnail_task] Arquivo encontrado em video.file.path: {video_path}")
        else:
            print(f"[extract_thumbnail_task] Arquivo não encontrado em nenhum local")
            print(f"[extract_thumbnail_task] Procurado em: {default_path}")
            if video.file:
                print(f"[extract_thumbnail_task] Procurado em: {video.file.path}")
            raise Exception(f"Video file not found for video {video_id}")
        
        # Abre o vídeo
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise Exception(f"Cannot open video file: {video_path}")
        
        # Obtém informações do vídeo
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if total_frames == 0:
            raise Exception("Video has no frames")
        
        # Extrai frame em 25% do tempo total
        frame_index = int(total_frames * 0.25)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise Exception("Cannot read frame from video")
        
        # Redimensiona para 320x180 (16:9)
        height, width = frame.shape[:2]
        aspect_ratio = width / height
        
        if aspect_ratio > 16/9:
            new_width = int(180 * aspect_ratio)
            new_height = 180
        else:
            new_width = 320
            new_height = int(320 / aspect_ratio)
        
        frame = cv2.resize(frame, (new_width, new_height))
        
        # Salva thumbnail em arquivo temporário
        thumbnail_dir = os.path.join(os.path.dirname(video_path), 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_path = os.path.join(thumbnail_dir, f"{video_id}_thumb.jpg")
        cv2.imwrite(thumbnail_path, frame)
        
        # Faz upload para R2
        storage = R2StorageService()
        print(f"[extract_thumbnail_task] Fazendo upload para R2")
        r2_thumbnail_path = storage.upload_thumbnail(thumbnail_path, video.organization_id, video_id)
        
        # Salva no banco com o caminho do R2
        video.thumbnail_storage_path = r2_thumbnail_path
        video.last_successful_step = "extracting_thumbnail"
        video.status = "normalizing"
        video.current_step = "normalizing"
        video.save()
        
        print(f"[extract_thumbnail_task] Thumbnail salvo com sucesso: {r2_thumbnail_path}")
        
        # Remove arquivo temporário
        try:
            os.remove(thumbnail_path)
        except:
            pass
        
        # Atualiza job status
        update_job_status(str(video_id), "normalizing", progress=20, current_step="normalizing")
        
        # Obtém organização para determinar a fila
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        # Dispara próxima task (normalize_video_task)
        from .normalize_video_task import normalize_video_task
        normalize_video_task.apply_async(
            args=[str(video_id)],
            queue=f"video.normalize.{org.plan}",
        )
        
        # Retorna video_id para logging
        return str(video_id)
        
    except Video.DoesNotExist:
        print(f"[extract_thumbnail_task] Video não encontrado: {video_id}")
        raise Exception(f"Video {video_id} not found")
    except Exception as e:
        print(f"[extract_thumbnail_task] Erro: {str(e)}")
        try:
            update_job_status(str(video_id), "extracting_thumbnail", "failed", str(e))
        except:
            pass
        
        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            print(f"[extract_thumbnail_task] Retentando em {2 ** self.request.retries}s")
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        else:
            print(f"[extract_thumbnail_task] Máximo de retentativas atingido")
