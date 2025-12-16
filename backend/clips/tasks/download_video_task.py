import logging
import os
import subprocess
import json
from celery import shared_task
from django.conf import settings

from ..models import Video, Organization
from ..services.storage_service import R2StorageService
from .job_utils import update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def download_video_task(self, video_id: str) -> dict:
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
        
        logger.info(f"Download concluído para video_id={video.video_id}")
        
        # Dispara próxima task (extract_thumbnail)
        from .extract_thumbnail_task import extract_thumbnail_task
        logger.info(f"Disparando extract_thumbnail_task para video_id={video.video_id}")
        task_result = extract_thumbnail_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.normalize.{org.plan}",
        )
        logger.info(f"extract_thumbnail_task disparada com task_id={task_result.id}")

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
    try:
        import yt_dlp
    except ImportError:
        raise Exception("yt-dlp não está instalado. Adicione à requirements.txt")

    output_template = os.path.join(output_dir, "video_download")

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": f"{output_template}.%(ext)s",
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([source_url])
    except Exception as e:
        raise Exception(f"Falha no download yt-dlp: {e}")

    expected_file = f"{output_template}.mp4"
    if not os.path.exists(expected_file):
        files = [f for f in os.listdir(output_dir) if f.startswith("video_download")]
        if not files:
            raise Exception("Arquivo de vídeo não encontrado após download")
        expected_file = os.path.join(output_dir, files[0])

    final_path = os.path.join(output_dir, "video_original.mp4")
    if expected_file != final_path:
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(expected_file, final_path)

    return final_path


def _validate_video(video_path: str) -> tuple:
    ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")
    timeout = 30

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "stream=codec_type,width,height,codec_name:format=duration",
            "-of", "json",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        
        data = json.loads(result.stdout)
        
        format_info = data.get('format', {})
        streams = data.get('streams', [])

        duration = float(format_info.get('duration', 0))
        
        video_stream = next((s for s in streams if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in streams if s['codec_type'] == 'audio'), None)

        if not video_stream:
            raise Exception("Arquivo não possui stream de vídeo válido")
        
        if not audio_stream:
            logger.warning(f"Vídeo {video_path} não possui áudio")

        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        codec = video_stream.get('codec_name', '')
        resolution = f"{width}x{height}"

        if duration < 5:
            raise Exception("Vídeo muito curto (mínimo 5 segundos)")
        if duration > 7200:
            raise Exception("Vídeo muito longo (máximo 2 horas)")
        if width < 240 or height < 240:
            raise Exception(f"Resolução muito baixa ({resolution}, mínimo 240p)")

        return duration, resolution, codec

    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout ao validar vídeo (ffprobe demorou mais de {timeout}s)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro ao validar vídeo: {e.stderr or e}")
    except Exception as e:
        raise Exception(f"Erro ao extrair metadados: {e}")
