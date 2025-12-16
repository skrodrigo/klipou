"""
Task para download de vídeo do R2 ou fonte externa.
Etapa: Downloading
"""

import os
import subprocess
from celery import shared_task, chain
from django.conf import settings
import requests

from ..models import Video, Job
from ..services.storage_service import R2StorageService
from .job_utils import update_job_status


@shared_task(bind=True, max_retries=5)
def download_video_task(self, video_id) -> dict:
    """
    Baixa vídeo do R2 ou da fonte externa (stream).
    
    Valida:
    - duração
    - tamanho
    - codec
    - resolução
    """
    try:
        # Procura vídeo por video_id (UUID)
        video = Video.objects.get(video_id=video_id)
        
        # Obtém organização
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "downloading"
        video.current_step = "downloading"
        video.save()
        
        # Atualiza job status
        update_job_status(str(video.video_id), "downloading", progress=10, current_step="downloading")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video.video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Se vídeo já está em R2, faz download
        if video.storage_path:
            storage = R2StorageService()
            local_path = os.path.join(output_dir, "video_original.mp4")
            # O storage_path é relativo ao bucket, então pode ser usado diretamente
            storage.download_file(video.storage_path, local_path)
            video_path = local_path
        # Se é fonte externa (YouTube, TikTok, etc)
        elif video.source_url:
            video_path = _download_from_source(video.source_url, output_dir)
        else:
            raise Exception("Nenhuma fonte de vídeo disponível")

        # Valida vídeo
        duration, resolution, codec = _validate_video(video_path)

        # Atualiza vídeo com metadados
        video.duration = duration
        video.resolution = resolution
        video.file_size = os.path.getsize(video_path)
        video.last_successful_step = "downloading"
        video.save()
        
        print(f"[download_video_task] Download concluído para video_id={video.video_id}")
        
        # Dispara próxima task (extract_thumbnail)
        from .extract_thumbnail_task import extract_thumbnail_task
        print(f"[download_video_task] Disparando extract_thumbnail_task para video_id={video.video_id}")
        task_result = extract_thumbnail_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.normalize.{org.plan}",
        )
        print(f"[download_video_task] extract_thumbnail_task disparada com task_id={task_result.id}")

        return {
            "video_id": str(video.video_id),
            "status": "normalizing",
            "duration": duration,
            "resolution": resolution,
            "file_size": video.file_size,
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "downloading"
        video.error_code = "DOWNLOAD_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _download_from_source(source_url: str, output_dir: str) -> str:
    """Baixa vídeo de fonte externa (YouTube, TikTok, etc)."""
    try:
        import yt_dlp
    except ImportError:
        raise Exception("yt-dlp não está instalado. Adicione à requirements.txt")

    output_path = os.path.join(output_dir, "video_original.mp4")

    ydl_opts = {
        "format": "best[ext=mp4]",
        "outtmpl": output_path,
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([source_url])
    except Exception as e:
        raise Exception(f"Falha ao baixar vídeo de {source_url}: {e}")

    if not os.path.exists(output_path):
        raise Exception("Arquivo de vídeo não foi criado após download")

    return output_path


def _validate_video(video_path: str) -> tuple:
    """Valida vídeo e extrai metadados usando um único comando ffprobe."""
    ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")
    timeout = 30  # Timeout de 30 segundos

    try:
        # Extrai tudo em um único comando (mais rápido) - apenas stream de vídeo
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration:stream=width,height,codec_name",
            "-of", "default=noprint_wrappers=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        
        # Parse output
        lines = result.stdout.strip().split('\n')
        data = {}
        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                data[key] = value
        
        duration = float(data.get('duration', 0))
        width = int(data.get('width', 0))
        height = int(data.get('height', 0))
        codec = data.get('codec_name', '')
        resolution = f"{width}x{height}"

        # Validações
        if duration < 1:
            raise Exception("Vídeo muito curto (mínimo 1 segundo)")
        if duration > 7200:  # 2 horas
            raise Exception("Vídeo muito longo (máximo 2 horas)")
        if width < 240 or height < 240:
            raise Exception(f"Resolução muito baixa ({resolution}, mínimo 240p)")
        if codec not in ["h264", "h265", "vp9"]:
            raise Exception(f"Codec de vídeo não suportado ({codec})")

        return duration, resolution, codec

    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout ao validar vídeo (ffprobe demorou mais de {timeout}s)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro ao validar vídeo: {e.stderr or e}")
    except Exception as e:
        raise Exception(f"Erro ao extrair metadados: {e}")
