import logging
import os
import glob
import subprocess
import json
from typing import Optional, Dict, Any, List
from celery import shared_task
from django.conf import settings

from ..models import Video, Organization
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)

DEFAULT_FFPROBE_TIMEOUT = 30
DEFAULT_FFMPEG_TIMEOUT = 1800
DEFAULT_MAX_WIDTH = 1920
DEFAULT_TARGET_FPS = 30.0
DEFAULT_CRF = 23
DEFAULT_PRESET = "veryfast"
DEFAULT_AUDIO_BITRATE = "128k"
DEFAULT_AUDIO_SAMPLE_RATE = "44100"
DEFAULT_PIX_FMT = "yuv420p"
DEFAULT_VIDEO_CODECS = "h264,h265"
DEFAULT_AUDIO_CODECS = "aac,mp3"
DEFAULT_MIN_FPS = 1.0
DEFAULT_MAX_FPS = 120.0


def _get_config(key: str, default: Any, type_cast=None) -> Any:
    try:
        val = getattr(settings, key, default)
        if val is None:
            return default
        if type_cast:
            return type_cast(val)
        return val
    except (ValueError, TypeError):
        logger.warning(f"Invalid config value for {key}, using default: {default}")
        return default


def _safe_update_job_status(
    video_id: str,
    status: str,
    *,
    progress: Optional[int] = None,
    current_step: Optional[str] = None
):
    try:
        update_job_status(video_id, status, progress=progress, current_step=current_step)
    except Exception as e:
        logger.warning(f"[normalize] update_job_status failed for {video_id}: {e}")


def _get_ffmpeg_path() -> str:
    return _get_config("FFMPEG_PATH", "ffmpeg", str)


def _get_ffprobe_path() -> str:
    ffprobe = _get_config("FFPROBE_PATH", None, str)
    if ffprobe:
        return ffprobe
    
    ffmpeg_path = _get_ffmpeg_path()
    return ffmpeg_path.replace("ffmpeg", "ffprobe")


@shared_task(bind=True, max_retries=5, acks_late=False)
def normalize_video_task(self, video_id: str) -> dict:
    video = None
    
    try:
        logger.info(f"[normalize] Iniciando para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "normalizing"
        video.current_step = "normalizing"
        video.save()

        _safe_update_job_status(
            str(video.video_id),
            "normalizing",
            progress=20,
            current_step="normalizing"
        )

        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(video_dir, exist_ok=True)

        input_path = _find_input_video(video_dir)
        
        if not input_path:
            raise FileNotFoundError(f"Arquivo de vídeo não encontrado em {video_dir}")

        logger.info(f"[normalize] Input: {input_path}")

        output_path = os.path.join(video_dir, "video_normalized.mp4")

        try:
            metadata = _probe_media(input_path)
            
            logger.info(
                f"[normalize] Metadata: codec={metadata.get('video_codec')} "
                f"audio={metadata.get('audio_codec')} fps={metadata.get('fps')} "
                f"res={metadata.get('width')}x{metadata.get('height')}"
            )
            
            if _is_fastpath_eligible(metadata):
                logger.info("[normalize] Using fast-path (remux)")
                _remux_copy(input_path, output_path)
            else:
                logger.info("[normalize] Using full normalization")
                _normalize_with_ffmpeg(input_path, output_path, metadata)
                
        except Exception as e:
            logger.warning(f"[normalize] Fast-path check failed, using full normalization: {e}")
            _normalize_with_ffmpeg(input_path, output_path, None)

        if not os.path.exists(output_path):
            raise RuntimeError("FFmpeg concluído mas arquivo normalizado não foi criado")

        output_size = os.path.getsize(output_path)
        if output_size <= 0:
            raise RuntimeError("Arquivo normalizado está vazio")

        resolution = _get_video_resolution(output_path)
        
        logger.info(
            f"[normalize] Output: {output_path} "
            f"size={output_size} resolution={resolution}"
        )

        video.file_size = output_size
        video.resolution = resolution
        video.last_successful_step = "normalizing"
        video.status = "transcribing"
        video.current_step = "transcribing"
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "transcribing",
            progress=30,
            current_step="transcribing"
        )

        from .transcribe_video_task import transcribe_video_task
        transcribe_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.transcribe.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "status": "transcribing",
            "resolution": resolution,
            "file_size": output_size,
        }

    except Video.DoesNotExist:
        logger.error(f"[normalize] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[normalize] Error for video_id={video_id}: {e}", exc_info=True)
        
        error_type = type(e).__name__
        
        if video:
            video.status = "failed"
            video.current_step = "normalizing"
            video.error_code = f"NORMALIZE_{error_type.upper()}"
            video.error_message = str(e)[:500]
            video.retry_count += 1
            video.save()

            if self.request.retries < self.max_retries:
                countdown = 2 ** self.request.retries
                logger.info(
                    f"[normalize] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                    f"in {countdown}s"
                )
                raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e)[:500], "status": "failed"}


def _find_input_video(video_dir: str) -> Optional[str]:
    
    preferred_name = os.path.join(video_dir, "video_original.mp4")
    if os.path.exists(preferred_name):
        return preferred_name
    
    patterns = _get_config(
        "NORMALIZE_INPUT_PATTERNS",
        "*.mp4,*.mkv,*.mov,*.webm,*.avi",
        str
    ).split(",")
    
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
            
        files = glob.glob(os.path.join(video_dir, pattern))
        if files:
            files.sort()
            return files[0]
    
    return None


def _normalize_with_ffmpeg(
    input_path: str,
    output_path: str,
    metadata: Optional[Dict[str, Any]]
) -> None:
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ffmpeg_path = _get_ffmpeg_path()
    ffmpeg_timeout = _get_config("FFMPEG_TIMEOUT", DEFAULT_FFMPEG_TIMEOUT, int)

    max_width = _get_config("NORMALIZE_MAX_WIDTH", DEFAULT_MAX_WIDTH, int)
    max_width = int(max(320, min(max_width, 7680)))
    
    target_fps = _get_config("NORMALIZE_TARGET_FPS", DEFAULT_TARGET_FPS, float)
    target_fps = float(max(1.0, min(target_fps, 120.0)))
    
    crf = _get_config("NORMALIZE_CRF", DEFAULT_CRF, int)
    crf = int(max(0, min(crf, 51)))
    
    preset = _get_config("NORMALIZE_PRESET", DEFAULT_PRESET, str)
    valid_presets = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
    if preset not in valid_presets:
        preset = DEFAULT_PRESET
    
    pix_fmt = _get_config("NORMALIZE_PIX_FMT", DEFAULT_PIX_FMT, str)
    audio_bitrate = _get_config("NORMALIZE_AUDIO_BITRATE", DEFAULT_AUDIO_BITRATE, str)
    audio_sample_rate = _get_config("NORMALIZE_AUDIO_SAMPLE_RATE", DEFAULT_AUDIO_SAMPLE_RATE, str)
    
    enable_loudnorm = _get_config("NORMALIZE_ENABLE_LOUDNORM", True, bool)
    
    input_fps = metadata.get("fps") if metadata else None
    
    should_change_fps = True
    if isinstance(input_fps, (int, float)) and input_fps > 0:
        fps_diff = abs(input_fps - target_fps)
        if fps_diff < 1.0:
            should_change_fps = False
            logger.info(f"[normalize] Keeping original FPS {input_fps} (close to target {target_fps})")
    
    vf_filters: List[str] = []
    
    vf_filters.append(f"scale='min({max_width},iw)':'-2'")
    
    vf_filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
    
    vf_filter = ",".join(vf_filters)
    
    af_filter = "anull"
    if enable_loudnorm:
        loudnorm_params = _get_config(
            "NORMALIZE_LOUDNORM_PARAMS",
            "I=-16:TP=-1.5:LRA=11",
            str
        )
        af_filter = f"loudnorm={loudnorm_params}"
        logger.info(f"[normalize] Audio normalization enabled: {af_filter}")

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pix_fmt,
        "-vf", vf_filter,
    ]
    
    if should_change_fps:
        cmd.extend(["-r", str(target_fps)])
    
    cmd.extend([
        "-c:a", "aac",
        "-ar", audio_sample_rate,
        "-b:a", audio_bitrate,
        "-af", af_filter,
        "-movflags", "+faststart",
        output_path,
    ])

    logger.debug(f"[normalize] FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=ffmpeg_timeout,
            text=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = (e.stderr if e.stderr else str(e))[:1000]
        logger.error(f"[normalize] FFmpeg failed: {error_msg}")
        
        if "libx264" in error_msg.lower():
            raise RuntimeError("FFmpeg não tem suporte a libx264. Instale ffmpeg com libx264.")
        elif "aac" in error_msg.lower():
            raise RuntimeError("FFmpeg não tem suporte a AAC. Instale ffmpeg com libfdk-aac ou aac nativo.")
        else:
            raise RuntimeError(f"FFmpeg falhou na normalização: {error_msg}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"[normalize] FFmpeg timeout after {ffmpeg_timeout}s")
        raise TimeoutError(f"Normalização excedeu {ffmpeg_timeout}s")


def _get_video_resolution(video_path: str) -> str:
    
    ffprobe_path = _get_ffprobe_path()

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            video_path,
        ]
        
        timeout = _get_config("FFPROBE_TIMEOUT", DEFAULT_FFPROBE_TIMEOUT, int)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        if not output:
            logger.warning("[normalize] FFprobe returned empty output")
            return "0x0"

        parts = output.split(",")
        if len(parts) != 2:
            logger.warning(f"[normalize] Unexpected FFprobe output: {output}")
            return "0x0"
            
        width = int(parts[0])
        height = int(parts[1])
        
        return f"{width}x{height}"
        
    except subprocess.TimeoutExpired:
        logger.error("[normalize] FFprobe timeout")
        return "0x0"
    except Exception as e:
        logger.warning(f"[normalize] Failed to get resolution: {e}")
        return "0x0"


def _probe_media(input_path: str) -> Dict[str, Any]:
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Cannot probe missing file: {input_path}")

    ffprobe_path = _get_ffprobe_path()
    timeout = _get_config("FFPROBE_TIMEOUT", DEFAULT_FFPROBE_TIMEOUT, int)

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )
        
        data = json.loads(result.stdout or "{}")
        
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"FFprobe timeout após {timeout}s")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"FFprobe retornou JSON inválido: {e}")
    except subprocess.CalledProcessError as e:
        error_msg = (e.stderr if e.stderr else str(e))[:500]
        raise RuntimeError(f"FFprobe failed: {error_msg}")

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def parse_fps(stream: Optional[Dict]) -> Optional[float]:
        if not stream:
            return None
            
        fps_str = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
        if not fps_str or fps_str == "0/0":
            return None
            
        try:
            if "/" in fps_str:
                num, den = fps_str.split("/")
                den_f = float(den)
                if den_f == 0:
                    return None
                return float(num) / den_f
            else:
                return float(fps_str)
        except (ValueError, ZeroDivisionError):
            return None

    return {
        "format_name": format_info.get("format_name"),
        "video_codec": (video_stream or {}).get("codec_name"),
        "audio_codec": (audio_stream or {}).get("codec_name"),
        "pix_fmt": (video_stream or {}).get("pix_fmt"),
        "fps": parse_fps(video_stream),
        "width": (video_stream or {}).get("width"),
        "height": (video_stream or {}).get("height"),
        "has_audio": bool(audio_stream),
        "has_video": bool(video_stream),
    }


def _is_fastpath_eligible(metadata: Dict[str, Any]) -> bool:
    
    if not metadata.get("has_video"):
        logger.info("[normalize] No video stream, not eligible for fast-path")
        return False

    video_codec = (metadata.get("video_codec") or "").lower()
    audio_codec = (metadata.get("audio_codec") or "").lower()
    fps = metadata.get("fps")

    allowed_video_codecs_str = _get_config(
        "NORMALIZE_FASTPATH_VIDEO_CODECS",
        DEFAULT_VIDEO_CODECS,
        str
    )
    allowed_video = set(c.strip().lower() for c in allowed_video_codecs_str.split(",") if c.strip())

    allowed_audio_codecs_str = _get_config(
        "NORMALIZE_FASTPATH_AUDIO_CODECS",
        DEFAULT_AUDIO_CODECS,
        str
    )
    allowed_audio = set(c.strip().lower() for c in allowed_audio_codecs_str.split(",") if c.strip())

    if video_codec not in allowed_video:
        logger.info(f"[normalize] Video codec '{video_codec}' not in allowed: {allowed_video}")
        return False

    if metadata.get("has_audio"):
        if audio_codec not in allowed_audio:
            logger.info(f"[normalize] Audio codec '{audio_codec}' not in allowed: {allowed_audio}")
            return False
    else:
        logger.info("[normalize] No audio stream (OK for fast-path)")

    if isinstance(fps, (int, float)):
        min_fps = _get_config("NORMALIZE_MIN_FPS", DEFAULT_MIN_FPS, float)
        max_fps = _get_config("NORMALIZE_MAX_FPS", DEFAULT_MAX_FPS, float)
        
        if fps < min_fps:
            logger.info(f"[normalize] FPS {fps} below minimum {min_fps}")
            return False
            
        if fps > max_fps:
            logger.info(f"[normalize] FPS {fps} above maximum {max_fps}")
            return False
    else:
        logger.warning("[normalize] FPS not detected, allowing fast-path")

    width = metadata.get("width")
    height = metadata.get("height")
    
    if isinstance(width, int) and isinstance(height, int):
        max_width = _get_config("NORMALIZE_MAX_WIDTH", DEFAULT_MAX_WIDTH, int)
        if width > max_width:
            logger.info(f"[normalize] Width {width} exceeds max {max_width}")
            return False

    logger.info("[normalize] Fast-path eligible")
    return True


def _remux_copy(input_path: str, output_path: str) -> None:
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ffmpeg_path = _get_ffmpeg_path()
    ffmpeg_timeout = _get_config("FFMPEG_TIMEOUT", DEFAULT_FFMPEG_TIMEOUT, int)

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

    logger.debug(f"[normalize] Remux command: {' '.join(cmd)}")

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=ffmpeg_timeout,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = (e.stderr if e.stderr else str(e))[:1000]
        logger.error(f"[normalize] Remux failed: {error_msg}")
        raise RuntimeError(f"Remux falhou: {error_msg}")
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Remux timeout após {ffmpeg_timeout}s")