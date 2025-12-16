import logging
import os
import glob
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Organization
from .job_utils import update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def normalize_video_task(self, video_id: str) -> dict:
    """
    Normaliza vídeo para formato padrão.
    
    Padroniza:
    - Áudio: 48kHz, mono ou estéreo, -3dB
    - FPS: 30fps
    - Resolução: mínimo 480p, máximo 1080p
    - Codec: H.264 para vídeo, AAC para áudio
    """
    try:
        logger.info(f"Iniciando normalização de vídeo para video_id: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "normalizing"
        video.current_step = "normalizing"
        video.save()

        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(video_dir, exist_ok=True)

        input_path = None
        potential_input = os.path.join(video_dir, "video_original.mp4")
        if os.path.exists(potential_input):
            input_path = potential_input
        else:
            patterns = ['*.mp4', '*.mkv', '*.mov', '*.webm', '*.avi']
            for p in patterns:
                files = glob.glob(os.path.join(video_dir, p))
                if files:
                    input_path = files[0]
                    break
        
        if not input_path:
            raise Exception(f"Arquivo de vídeo original não encontrado em {video_dir}")

        output_path = os.path.join(video_dir, "video_normalized.mp4")

        _normalize_with_ffmpeg(input_path, output_path)

        if not os.path.exists(output_path):
            raise Exception("FFmpeg finalizou mas arquivo normalized não foi criado")

        resolution = _get_video_resolution(output_path)
        file_size = os.path.getsize(output_path)

        video.file_size = file_size
        video.resolution = resolution
        video.last_successful_step = "normalizing"
        video.status = "transcribing"
        video.current_step = "transcribing"
        video.save()
        
        update_job_status(str(video.video_id), "transcribing", progress=30, current_step="transcribing")

        from .transcribe_video_task import transcribe_video_task
        transcribe_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.transcribe.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "status": "transcribing",
            "resolution": resolution,
        }

    except Video.DoesNotExist:
        logger.error(f"Vídeo não encontrado: {video_id}")
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro na normalização do vídeo {video_id}: {e}")
        if video:
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
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 1800))

    vf_filter = "scale='min(1920,iw)':'-2',pad=ceil(iw/2)*2:ceil(ih/2)*2"

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", input_path,
        
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-vf", vf_filter,
        
        "-c:a", "aac",
        "-ar", "44100",
        "-b:a", "128k",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        
        "-movflags", "+faststart",
        
        output_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=ffmpeg_timeout,
            text=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"FFmpeg falhou: {error_msg}")
        raise Exception(f"FFmpeg falhou: {error_msg}")
    except subprocess.TimeoutExpired:
        raise Exception(f"Normalização excedeu o tempo limite de {ffmpeg_timeout}s")


def _get_video_resolution(video_path: str) -> str:
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
        
        output = result.stdout.strip()
        if not output:
            return "0x0"
            
        width, height = map(int, output.split(","))
        return f"{width}x{height}"
    except Exception as e:
        logger.warning(f"Não foi possível extrair resolução de {video_path}: {e}")
        return "0x0"
