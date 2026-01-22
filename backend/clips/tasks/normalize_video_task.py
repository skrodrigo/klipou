import logging
import os
import glob
import subprocess
import json
from celery import shared_task
from django.conf import settings

from ..models import Video, Organization
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, acks_late=False)
def normalize_video_task(self, video_id: str) -> dict:
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

        # Fast-path: se já estiver num formato compatível, apenas remux/copy.
        # Isso evita recompressão (qualidade idêntica) e é muito mais rápido.
        try:
            metadata = _probe_media(input_path)
            if _is_fastpath_eligible(metadata):
                logger.info(
                    f"[normalize] Fast-path remux para {video_id}: "
                    f"v={metadata.get('video_codec')} a={metadata.get('audio_codec')} fps={metadata.get('fps')}"
                )
                _remux_copy(input_path, output_path)
            else:
                _normalize_with_ffmpeg(input_path, output_path)
        except Exception as e:
            logger.warning(f"[normalize] Fast-path falhou/indisponível, usando normalização completa: {e}")
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
            queue=f"video.transcribe.{get_plan_tier(org.plan)}",
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


def _probe_media(input_path: str) -> dict:
    ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")
    timeout = 30

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])

    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def _parse_fps(s: dict | None) -> float | None:
        if not s:
            return None
        # avg_frame_rate vem como "30000/1001" etc.
        fr = s.get("avg_frame_rate") or s.get("r_frame_rate")
        if not fr or fr == "0/0":
            return None
        try:
            num, den = fr.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except Exception:
            return None

    return {
        "format_name": (data.get("format", {}) or {}).get("format_name"),
        "video_codec": (v or {}).get("codec_name"),
        "audio_codec": (a or {}).get("codec_name"),
        "pix_fmt": (v or {}).get("pix_fmt"),
        "fps": _parse_fps(v),
        "width": (v or {}).get("width"),
        "height": (v or {}).get("height"),
        "has_audio": bool(a),
    }


def _is_fastpath_eligible(metadata: dict) -> bool:
    # Critérios conservadores: só quando temos muita certeza.
    video_codec = (metadata.get("video_codec") or "").lower()
    audio_codec = (metadata.get("audio_codec") or "").lower()
    fps = metadata.get("fps")

    if video_codec not in {"h264"}:
        return False
    # Se não tiver áudio, ainda podemos fazer copy (mantém sem áudio).
    if metadata.get("has_audio") and audio_codec not in {"aac"}:
        return False
    # Evitar casos muito estranhos de fps.
    if isinstance(fps, (int, float)):
        if fps <= 0:
            return False
        if fps > 61:
            return False
    return True


def _remux_copy(input_path: str, output_path: str) -> None:
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 1800))

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=ffmpeg_timeout,
        text=True,
    )
