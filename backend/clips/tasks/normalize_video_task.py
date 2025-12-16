"""
Task para normalização de vídeo.
Etapa: Normalizing
Converte vídeo para formato padrão (codec, resolução, frame rate).
"""

import os
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript
from ..services.storage_service import R2StorageService
from .job_utils import update_job_status


@shared_task(bind=True, max_retries=5)
def normalize_video_task(self, video_id: int) -> dict:
    """
    Normaliza vídeo para formato padrão.
    
    Padroniza:
    - Áudio: 48kHz, mono ou estéreo, -3dB
    - FPS: 30fps
    - Resolução: mínimo 480p, máximo 1080p
    - Codec: H.264 para vídeo, AAC para áudio
    """
    try:
        # Procura vídeo por video_id (UUID)
        video = Video.objects.get(video_id=video_id)
        
        # Obtém organização
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "normalizing"
        video.current_step = "normalizing"
        video.save()

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Arquivo original (já baixado na etapa anterior)
        input_path = os.path.join(output_dir, "video_original.mp4")
        output_path = os.path.join(output_dir, "video_normalized.mp4")

        if not os.path.exists(input_path):
            raise Exception("Arquivo de vídeo original não encontrado")

        # Normaliza vídeo
        _normalize_with_ffmpeg(input_path, output_path)

        # Calcula resolução final
        resolution = _get_video_resolution(output_path)

        # Atualiza vídeo
        video.file_size = os.path.getsize(output_path)
        video.resolution = resolution
        video.last_successful_step = "normalizing"
        video.status = "transcribing"
        video.current_step = "transcribing"
        video.save()
        
        # Atualiza job status
        update_job_status(str(video.video_id), "transcribing", progress=30, current_step="transcribing")

        # Dispara próxima task (transcribing)
        from .transcribe_video_task import transcribe_video_task
        transcribe_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.transcribe.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "status": "transcribing",
            "file_size": video.file_size,
            "resolution": resolution,
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "normalizing"
        video.error_code = "NORMALIZATION_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _normalize_with_ffmpeg(input_path: str, output_path: str) -> None:
    """Normaliza vídeo com FFmpeg."""
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 600))

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", input_path,
        # Vídeo: H.264, 30fps, máximo 1080p
        "-c:v", "libx264",
        "-r", "30",
        "-vf", "scale=min(1920\\,iw):min(1080\\,ih):force_original_aspect_ratio=decrease",
        "-preset", "medium",
        # Áudio: AAC, 48kHz, -3dB
        "-c:a", "aac",
        "-ar", "48000",
        "-af", "volume=-3dB",
        # Saída
        output_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ffmpeg_timeout,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg falhou ao normalizar vídeo: {e}")
    except subprocess.TimeoutExpired:
        raise Exception("Normalização de vídeo excedeu o tempo limite")

    if not os.path.exists(output_path):
        raise Exception("Arquivo normalizado não foi criado")


def _get_video_resolution(video_path: str) -> str:
    """Extrai resolução do vídeo."""
    ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(","))
        return f"{width}x{height}"
    except Exception as e:
        raise Exception(f"Erro ao extrair resolução: {e}")
