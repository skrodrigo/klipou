import logging
import os
import subprocess
import json
import shutil
import time
from celery import shared_task
from django.conf import settings

from ..models import Video, Organization
from ..services.storage_service import R2StorageService
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, acks_late=False)
def download_video_task(self, video_id: str) -> dict:
    video = None
    temp_dir = None
    lock_path = None
    lock_owner_pid = None
    
    try:
        video = Video.objects.get(video_id=video_id)
        
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "downloading"
        video.current_step = "downloading"
        video.save()
        
        update_job_status(str(video.video_id), "downloading", progress=10, current_step="downloading")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video.video_id}")
        os.makedirs(output_dir, exist_ok=True)
        temp_dir = output_dir

        lock_path = os.path.join(output_dir, ".download.lock")
        lock_owner_pid = int(os.getpid())
        stale_seconds = int(getattr(settings, "DOWNLOAD_LOCK_STALE_SECONDS", 900) or 900)
        try:
            if os.path.exists(lock_path):
                try:
                    mtime = float(os.path.getmtime(lock_path) or 0)
                    if (time.time() - mtime) > float(stale_seconds):
                        os.remove(lock_path)
                except Exception:
                    pass

            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(lock_owner_pid).encode("utf-8"))
            os.close(lock_fd)
        except FileExistsError:
            logger.info(f"Download já em andamento para video_id={video.video_id}. Ignorando.")
            return {"video_id": str(video.video_id), "status": "downloading", "detail": "already_running"}

        storage = R2StorageService()
        local_video_path = os.path.join(output_dir, "video_original.mp4")

        if video.storage_path:
            logger.info(f"Baixando vídeo do R2: {video.storage_path}")
            storage.download_file(video.storage_path, local_video_path)
            video_path = local_video_path

        elif video.source_url:
            logger.info(f"Baixando vídeo de URL externa: {video.source_url} (tipo: {video.source_type})")

            downloaded = _download_from_source_url(
                source_url=video.source_url,
                output_dir=output_dir,
            )
            video_path = downloaded["video_path"]
            info = downloaded.get("info") or {}

            logger.info(
                "Download retornou caminho=%s size=%s bytes",
                video_path,
                os.path.getsize(video_path) if os.path.exists(video_path) else "<missing>",
            )

            if video_path != local_video_path:
                if os.path.exists(local_video_path):
                    os.remove(local_video_path)

                update_job_status(
                    str(video.video_id),
                    "downloading",
                    progress=12,
                    current_step="moving_downloaded_file",
                )
                logger.info("Movendo arquivo baixado para %s", local_video_path)
                shutil.move(video_path, local_video_path)
                video_path = local_video_path
                logger.info(
                    "Arquivo movido. size=%s bytes",
                    os.path.getsize(video_path) if os.path.exists(video_path) else "<missing>",
                )

            original_filename = _guess_original_filename(info, fallback="video_original.mp4")
            video.original_filename = original_filename

            if not video.title:
                video.title = _guess_title_from_ydl_info(info, fallback=f"Video from {video.source_type or 'url'}")

            if not video.storage_path:
                try:
                    update_job_status(
                        str(video.video_id),
                        "downloading",
                        progress=13,
                        current_step="enqueue_upload_original_to_r2",
                    )
                    # Persist metadata early; upload will run async.
                    video.save()

                    from .upload_original_video_task import upload_original_video_task
                    upload_original_video_task.apply_async(
                        args=[str(video.video_id)],
                        queue=f"video.download.{get_plan_tier(org.plan)}",
                    )
                except Exception as e:
                    logger.warning(f"Falha ao enfileirar upload async do vídeo original para o R2: {e}")
        else:
            raise Exception("Nenhuma fonte de vídeo disponível (storage_path ou source_url)")

        update_job_status(str(video.video_id), "downloading", progress=14, current_step="validating_video")
        logger.info(f"Validando vídeo: {video_path}")
        duration, resolution, codec = _validate_video(video_path)

        video.duration = duration
        video.resolution = resolution
        video.file_size = os.path.getsize(video_path)
        video.last_successful_step = "downloading"

        video.save()
        
        logger.info(f"Download concluído para video_id={video.video_id} | "
                   f"Duração: {duration}s | Resolução: {resolution} | Codec: {codec}")
        
        from .extract_thumbnail_task import extract_thumbnail_task
        logger.info(f"Disparando extract_thumbnail_task para video_id={video.video_id}")
        task_result = extract_thumbnail_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.normalize.{get_plan_tier(org.plan)}",
        )
        logger.info(f"extract_thumbnail_task disparada com task_id={task_result.id}")

        return {
            "video_id": str(video.video_id),
            "status": "downloading",
            "duration": duration,
            "resolution": resolution,
            "file_size": video.file_size,
            "codec": codec,
        }

    except Video.DoesNotExist:
        logger.error(f"Vídeo não encontrado: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"Erro ao baixar vídeo {video_id}: {str(e)}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.current_step = "downloading"
            error_code = _get_error_code(str(e))
            video.error_code = error_code
            video.error_message = str(e)
            video.retry_count += 1
            video.save()

            update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="downloading",
            )

            permanent_codes = {
                "VIDEO_PRIVATE",
                "VIDEO_NOT_FOUND",
                "GEO_BLOCKED",
                "AUTH_REQUIRED",
                "FORBIDDEN",
                "TOO_MANY_REQUESTS",
            }

            if error_code in permanent_codes:
                return {"error": str(e), "status": "failed", "error_code": error_code}

            if self.request.retries < self.max_retries:
                countdown = 2 ** self.request.retries
                logger.warning(f"Retentando download em {countdown}s (tentativa {self.request.retries + 1}/{self.max_retries})")
                raise self.retry(exc=e, countdown=countdown)

        if temp_dir:
            _cleanup_temp_download_files(temp_dir)

        return {"error": str(e), "status": "failed"}

    finally:
        if lock_path and os.path.exists(lock_path):
            try:
                content = ""
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        content = (f.read() or "").strip()
                except Exception:
                    content = ""

                if str(lock_owner_pid or "") and content == str(lock_owner_pid):
                    os.remove(lock_path)
            except Exception:
                pass


def _download_from_source_url(source_url: str, output_dir: str) -> dict:
    try:
        import yt_dlp
    except ImportError:
        raise Exception("yt-dlp não está instalado. Adicione à requirements.txt")

    tmp_subdir = os.path.join(output_dir, "_yt_dlp")
    if os.path.isdir(tmp_subdir):
        try:
            shutil.rmtree(tmp_subdir, ignore_errors=True)
        except Exception:
            pass
    os.makedirs(tmp_subdir, exist_ok=True)
    output_template = os.path.join(tmp_subdir, "download.%(ext)s")

    proxy_url = os.getenv("PROXY_URL")
    user_agent = os.getenv("YTDLP_USER_AGENT")
    referer = os.getenv("YTDLP_REFERER")

    concurrent_frags = int(getattr(settings, "YTDLP_CONCURRENT_FRAGMENT_DOWNLOADS", 4) or 4)
    http_chunk_size = int(getattr(settings, "YTDLP_HTTP_CHUNK_SIZE", 10 * 1024 * 1024) or (10 * 1024 * 1024))
    sleep_interval = float(getattr(settings, "YTDLP_SLEEP_INTERVAL", 0) or 0)
    max_sleep_interval = float(getattr(settings, "YTDLP_MAX_SLEEP_INTERVAL", 0) or 0)
    extractor_retries = int(getattr(settings, "YTDLP_EXTRACTOR_RETRIES", 3) or 3)

    max_height = int(getattr(settings, "YTDLP_MAX_HEIGHT", 720) or 720)
    # Prefer H.264 (avc1) + m4a, but cap resolution for speed.
    fmt = (
        f"bv*[ext=mp4][vcodec^=avc1][height<={max_height}]+ba[ext=m4a]/"
        f"bv*[ext=mp4][height<={max_height}]+ba[ext=m4a]/"
        f"b[ext=mp4][height<={max_height}]/"
        f"bv*+ba/b"
    )

    ydl_opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "retries": extractor_retries,
        "fragment_retries": extractor_retries,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": concurrent_frags,
        "http_chunk_size": http_chunk_size,
        "continuedl": False,
        "nopart": True,
        "keepvideo": True,
        "consoletitle": False,
        "quiet": True,
        "no_warnings": True,
    }

    if proxy_url:
        ydl_opts["proxy"] = proxy_url

    if user_agent:
        ydl_opts["user_agent"] = user_agent

    if referer:
        ydl_opts["referer"] = referer

    if sleep_interval and sleep_interval > 0:
        ydl_opts["sleep_interval"] = sleep_interval
        if max_sleep_interval and max_sleep_interval > 0:
            ydl_opts["max_sleep_interval"] = max_sleep_interval

    try:
        logger.info(f"Iniciando download via yt-dlp: {source_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=True)
            logger.info(f"yt-dlp ok: {info.get('title', 'Unknown')}")

    except yt_dlp.utils.DownloadError as e:
        raise Exception(_map_yt_dlp_error_to_message(str(e), source_url))
    except Exception as e:
        raise Exception(f"Falha no download yt-dlp: {str(e)}")

    final_path = _find_downloaded_media_file(tmp_subdir)
    if not final_path:
        raise Exception("Arquivo de vídeo não encontrado após download")

    return {"video_path": final_path, "info": info}


def _find_downloaded_media_file(download_dir: str) -> str | None:
    try:
        candidates = []
        for name in os.listdir(download_dir):
            p = os.path.join(download_dir, name)
            if os.path.isdir(p):
                continue
            lower = name.lower()
            if lower.endswith((".mp4", ".mkv", ".mov", ".webm")):
                candidates.append(p)
        if not candidates:
            return None
        candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
        return candidates[0]
    except FileNotFoundError:
        return None


def _map_yt_dlp_error_to_message(error_msg: str, source_url: str) -> str:
    msg = (error_msg or "").lower()

    if "403" in msg or "forbidden" in msg:
        return "YouTube bloqueou temporariamente este download (403). Tente novamente em alguns minutos."
    if "429" in msg or "too many requests" in msg:
        return "Muitas tentativas seguidas (429). Aguarde alguns minutos e tente novamente."
    if "private" in msg or "login" in msg or "sign in" in msg:
        return f"Vídeo privado, requer login, ou não acessível: {source_url}"
    if "not available" in msg or "404" in msg or "removed" in msg:
        return f"Vídeo não disponível ou foi removido: {source_url}"
    if "geo" in msg or "not available in your country" in msg:
        return "Vídeo bloqueado por localização geográfica"
    if "proxy" in msg:
        return "Erro relacionado a proxy"
    if "timeout" in msg or "timed out" in msg:
        return "Timeout ao baixar o vídeo. Verifique sua conexão e tente novamente."
    return f"Erro ao baixar vídeo via yt-dlp: {error_msg}"


def _guess_title_from_ydl_info(info: dict, fallback: str) -> str:
    title = (info or {}).get("title")
    if title and isinstance(title, str):
        return title[:255]
    return fallback[:255]


def _guess_original_filename(info: dict, fallback: str) -> str:
    ext = (info or {}).get("ext")
    if ext and isinstance(ext, str):
        safe_ext = ext.lower()
        if safe_ext in ("mp4", "mkv", "mov", "webm"):
            return f"video_original.{safe_ext}"
    return fallback


def _cleanup_temp_download_files(output_dir: str) -> None:
    tmp_subdir = os.path.join(output_dir, "_yt_dlp")
    if os.path.isdir(tmp_subdir):
        try:
            shutil.rmtree(tmp_subdir, ignore_errors=True)
        except Exception:
            pass


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

        logger.info(f"Vídeo validado: {resolution} | {codec} | {duration}s")
        return duration, resolution, codec

    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout ao validar vídeo (ffprobe demorou mais de {timeout}s)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro ao validar vídeo: {e.stderr or e}")
    except Exception as e:
        raise Exception(f"Erro ao extrair metadados: {e}")


def _get_error_code(error_message: str) -> str:
    """
    Mapeia mensagem de erro para código de erro.
    
    Usado para categorizar erros e facilitar debugging.
    """
    error_lower = error_message.lower()
    
    if "private" in error_lower or "not accessible" in error_lower:
        return "VIDEO_PRIVATE"
    elif "not available" in error_lower or "removed" in error_lower:
        return "VIDEO_NOT_FOUND"
    elif "geo" in error_lower or "blocked" in error_lower:
        return "GEO_BLOCKED"
    elif "proxy" in error_lower:
        return "PROXY_ERROR"
    elif "timeout" in error_lower or "socket" in error_lower:
        return "NETWORK_TIMEOUT"
    elif "too short" in error_lower or "too long" in error_lower:
        return "INVALID_DURATION"
    elif "resolution" in error_lower or "codec" in error_lower:
        return "INVALID_FORMAT"
    elif "upload" in error_lower or "r2" in error_lower:
        return "STORAGE_ERROR"
    else:
        return "DOWNLOAD_ERROR"
