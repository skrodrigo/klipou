"""
Task para download de vídeo do R2 ou fonte externa.
Etapa: Downloading
"""

import os
import subprocess
from celery import shared_task
from django.conf import settings
import requests

from ..models import Video
from ..services.storage_service import R2StorageService


@shared_task(bind=True, max_retries=5)
def download_video_task(self, video_id: int) -> dict:
    """
    Baixa vídeo do R2 ou da fonte externa (stream).
    
    Valida:
    - duração
    - tamanho
    - codec
    - resolução
    """
    try:
        video = Video.objects.get(id=video_id)
        video.status = "downloading"
        video.current_step = "downloading"
        video.save()

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Se vídeo já está em R2, faz download
        if video.storage_path:
            storage = R2StorageService()
            local_path = os.path.join(output_dir, "video_original.mp4")
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

        return {
            "video_id": video_id,
            "status": "downloading",
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
    """Valida vídeo e extrai metadados."""
    ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")

    try:
        # Extrai duração
        cmd_duration = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())

        # Extrai resolução
        cmd_resolution = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd_resolution, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(","))
        resolution = f"{width}x{height}"

        # Extrai codec
        cmd_codec = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd_codec, capture_output=True, text=True, check=True)
        codec = result.stdout.strip()

        # Validações
        if duration < 1:
            raise Exception("Vídeo muito curto (mínimo 1 segundo)")
        if duration > 7200:  # 2 horas
            raise Exception("Vídeo muito longo (máximo 2 horas)")
        if width < 480 or height < 480:
            raise Exception(f"Resolução muito baixa ({resolution}, mínimo 480p)")
        if codec not in ["h264", "h265", "vp9"]:
            raise Exception(f"Codec não suportado ({codec})")

        return duration, resolution, codec

    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro ao validar vídeo: {e}")
    except Exception as e:
        raise Exception(f"Erro ao extrair metadados: {e}")
