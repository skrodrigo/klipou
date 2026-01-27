import logging
import os
import uuid
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import Video, Clip, Transcript, Organization, Job, Schedule
from .job_utils import update_job_status
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)

DEFAULT_END_PAD_SECONDS = 0.0
DEFAULT_MIN_CLIP_DURATION = 1.0
DEFAULT_MAX_WORKERS = 4
DEFAULT_FFMPEG_TIMEOUT = 600
DEFAULT_TARGET_HEIGHT = 720
DEFAULT_CRF = 21
DEFAULT_PRESET = "medium"
DEFAULT_AUDIO_BITRATE = "192k"


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
        logger.warning(f"[clip_gen] update_job_status failed for {video_id}: {e}")


def _to_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _normalize_score_to_0_100(raw_score: float) -> float:
    try:
        score = float(raw_score)
        if score <= 10.0:
            score = score * 10.0
        return float(max(0.0, min(score, 100.0)))
    except (ValueError, TypeError):
        return 0.0


def _validate_crop_config(crop_config: Optional[Dict]) -> Optional[Dict[str, int]]:
    if not crop_config or not isinstance(crop_config, dict):
        return None
    
    try:
        w = int(crop_config.get("width", 0))
        h = int(crop_config.get("height", 0))
        x = int(crop_config.get("x", 0))
        y = int(crop_config.get("y", 0))
        
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            return None
            
        return {"width": w, "height": h, "x": x, "y": y}
    except (ValueError, TypeError):
        return None


@shared_task(bind=True, max_retries=5, acks_late=False)
def clip_generation_task(self, video_id: str) -> dict:
    video = None
    
    try:
        logger.info(f"[clip_gen] Iniciando para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)

        job = (
            Job.objects.filter(video_id=video.video_id, organization_id=video.organization_id)
            .order_by("-created_at")
            .first()
        )
        job_config = (job.configuration if job and isinstance(job.configuration, dict) else {})
        auto_schedule = bool(job_config.get("autoSchedule") or job_config.get("auto_schedule"))
        auto_platform = str(job_config.get("auto_schedule_platform") or "tiktok")

        video.status = "rendering"
        video.current_step = "rendering"
        video.save()

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise ValueError("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        caption_files = transcript.caption_files or []
        reframe_data = transcript.reframe_data or {}
        
        if not selected_clips:
            raise ValueError("Nenhum clip para renderizar")

        crop_config_raw = reframe_data.get("crops", {}).get("9:16")
        crop_config = _validate_crop_config(crop_config_raw)
        
        if crop_config_raw and not crop_config:
            logger.warning("[clip_gen] Crop config inválido, ignorando crop")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        captions_dir = os.path.join(output_dir, "captions")
        os.makedirs(captions_dir, exist_ok=True)

        input_path = os.path.join(output_dir, "video_normalized.mp4")
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Vídeo normalizado não encontrado: {input_path}")

        storage = R2StorageService()
        generated_clips: List[Dict[str, str]] = []
        failures: List[Dict[str, Any]] = []

        total_clips = len(selected_clips)
        end_pad_s = _get_config("CLIP_END_PAD_SECONDS", DEFAULT_END_PAD_SECONDS, float)
        min_clip_duration_s = _get_config("CLIP_MIN_DURATION_SECONDS", DEFAULT_MIN_CLIP_DURATION, float)
        
        video_duration = _to_float(video.duration, 0.0) if video.duration else 0.0

        render_jobs: List[Dict[str, Any]] = []
        
        for idx, clip in enumerate(selected_clips):
            clip_uuid = uuid.uuid4()
            start_time = _to_float(clip.get("start_time"), 0.0)
            end_time = _to_float(clip.get("end_time"), 0.0)

            if end_pad_s > 0:
                padded_end = end_time + end_pad_s
                if video_duration > 0:
                    end_time = min(padded_end, video_duration)
                else:
                    end_time = padded_end

            if end_time <= start_time:
                logger.warning(
                    f"[clip_gen] Clip {idx} timestamps inválidos: "
                    f"start={start_time} end={end_time}, pulando"
                )
                failures.append({
                    "idx": idx,
                    "error": "invalid_timestamps",
                    "start": start_time,
                    "end": end_time,
                })
                continue

            duration = end_time - start_time
            if duration < min_clip_duration_s:
                logger.warning(
                    f"[clip_gen] Clip {idx} muito curto: "
                    f"duration={duration:.2f}s < min={min_clip_duration_s}s, pulando"
                )
                failures.append({
                    "idx": idx,
                    "error": "duration_too_short",
                    "duration": duration,
                })
                continue

            hook_title = clip.get("title") or clip.get("hook_title") or f"Clip {idx + 1}"
            matched_caption = next(
                (
                    c
                    for c in caption_files
                    if isinstance(c, dict)
                    and str(c.get("kind") or "").lower() == "ass"
                    and int(c.get("index", -1)) == int(idx)
                ),
                None,
            )
            ass_file = None
            if isinstance(matched_caption, dict):
                cap_path = matched_caption.get("path")
                if isinstance(cap_path, str) and cap_path:
                    local_ass = os.path.join(captions_dir, f"caption_{idx}.ass")
                    try:
                        storage.download_file(str(cap_path), local_ass)
                        if os.path.exists(local_ass) and os.path.getsize(local_ass) > 0:
                            ass_file = local_ass
                    except Exception as e:
                        logger.warning(f"[clip_gen] Falha ao baixar ASS do R2 para clip {idx}: {e}")

            clip_filename = f"clip_{clip_uuid}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)

            render_jobs.append({
                "idx": idx,
                "clip_uuid": clip_uuid,
                "clip_path": clip_path,
                "start_time": start_time,
                "end_time": end_time,
                "hook_title": hook_title,
                "ass_file": ass_file,
                "transcript_text": str(clip.get("text", ""))[:5000],
                "score_raw": _to_float(clip.get("score"), 0.0),
            })

        if not render_jobs:
            error_msg = (
                f"Nenhum clip válido para renderizar. "
                f"Total: {total_clips}, Falhas: {len(failures)}"
            )
            logger.error(f"[clip_gen] {error_msg}")
            raise ValueError(error_msg)

        logger.info(
            f"[clip_gen] Renderizando {len(render_jobs)} clips "
            f"({len(failures)} rejeitados)"
        )

        max_workers = _get_config("CLIP_RENDER_MAX_WORKERS", None, int)
        if not max_workers or max_workers <= 0:
            cpu_count = os.cpu_count() or 2
            max_workers = max(1, min(DEFAULT_MAX_WORKERS, cpu_count))
        
        max_workers = int(max(1, min(max_workers, 8)))

        completed = 0
        _safe_update_job_status(
            str(video.video_id),
            "rendering",
            progress=85,
            current_step="rendering"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {
                executor.submit(
                    _render_clip,
                    input_path,
                    job["clip_path"],
                    job["start_time"],
                    job["end_time"],
                    crop_config,
                    job["ass_file"],
                ): job
                for job in render_jobs
            }

            for future in as_completed(future_to_job):
                job = future_to_job[future]
                
                try:
                    future.result()
                except Exception as e:
                    failures.append({
                        "idx": job["idx"],
                        "error": str(e)[:200],
                    })
                    logger.error(f"[clip_gen] Render failed for clip {job['idx']}: {e}")
                    
                    if os.path.exists(job["clip_path"]):
                        try:
                            os.remove(job["clip_path"])
                            logger.debug(f"[clip_gen] Removed failed clip file: {job['clip_path']}")
                        except Exception as cleanup_err:
                            logger.warning(f"[clip_gen] Failed to cleanup: {cleanup_err}")
                    continue

                completed += 1
                progress = 85 + int((completed / max(1, len(render_jobs))) * 10)
                progress = int(max(85, min(progress, 99)))
                
                _safe_update_job_status(
                    str(video.video_id),
                    "rendering",
                    progress=progress,
                    current_step=f"rendering_clip_{completed}/{len(render_jobs)}",
                )

                clip_path = job["clip_path"]
                
                if not os.path.exists(clip_path):
                    failures.append({
                        "idx": job["idx"],
                        "error": "clip_file_not_found_after_render",
                    })
                    logger.error(f"[clip_gen] Clip file missing after render: {clip_path}")
                    continue
                
                file_size = os.path.getsize(clip_path)
                
                if file_size <= 0:
                    failures.append({
                        "idx": job["idx"],
                        "error": "clip_file_empty",
                    })
                    logger.error(f"[clip_gen] Clip file is empty: {clip_path}")
                    try:
                        os.remove(clip_path)
                    except Exception:
                        pass
                    continue

                try:
                    clip_storage_path = storage.upload_clip(
                        file_path=clip_path,
                        organization_id=str(video.organization_id),
                        video_id=str(video.video_id),
                        clip_id=str(job["clip_uuid"]),
                    )
                except Exception as upload_err:
                    failures.append({
                        "idx": job["idx"],
                        "error": f"upload_failed: {str(upload_err)[:100]}",
                    })
                    logger.error(f"[clip_gen] Upload failed for clip {job['idx']}: {upload_err}")
                    
                    try:
                        os.remove(clip_path)
                    except Exception:
                        pass
                    continue

                if not clip_storage_path:
                    failures.append({
                        "idx": job["idx"],
                        "error": "upload_returned_empty_path",
                    })
                    logger.error(f"[clip_gen] Upload returned empty path for clip {job['idx']}")
                    try:
                        os.remove(clip_path)
                    except Exception:
                        pass
                    continue

                score_0_100 = _normalize_score_to_0_100(job.get("score_raw", 0.0))

                try:
                    Clip.objects.create(
                        clip_id=job["clip_uuid"],
                        job=job if job else None,
                        video=video,
                        title=job["hook_title"],
                        start_time=job["start_time"],
                        end_time=job["end_time"],
                        duration=job["end_time"] - job["start_time"],
                        storage_path=clip_storage_path,
                        file_size=file_size,
                        transcript=job["transcript_text"],
                        engagement_score=round(score_0_100, 2),
                        confidence_score=0,
                    )
                except Exception as db_err:
                    failures.append({
                        "idx": job["idx"],
                        "error": f"database_create_failed: {str(db_err)[:100]}",
                    })
                    logger.error(f"[clip_gen] Failed to create Clip in DB: {db_err}")
                    continue

                generated_clips.append({
                    "clip_id": str(job["clip_uuid"]),
                    "url": clip_storage_path,
                })

                try:
                    os.remove(clip_path)
                    logger.debug(f"[clip_gen] Removed local clip file: {clip_path}")
                except Exception as cleanup_err:
                    logger.warning(f"[clip_gen] Failed to remove local file: {cleanup_err}")

        if not generated_clips:
            error_msg = (
                f"Nenhum clip renderizado com sucesso. "
                f"Total jobs: {len(render_jobs)}, "
                f"Falhas: {len(failures)}"
            )
            logger.error(f"[clip_gen] {error_msg}")
            logger.error(f"[clip_gen] Primeiras falhas: {failures[:5]}")
            raise RuntimeError(error_msg)

        logger.info(
            f"[clip_gen] Concluído para video_id={video_id}: "
            f"{len(generated_clips)} clips gerados, {len(failures)} falhas"
        )

        if auto_schedule:
            try:
                created = 0
                base_time = timezone.now()
                # agendar a partir do próximo slot de 30 minutos
                minute = int(base_time.minute)
                snap = 30
                add_min = (snap - (minute % snap)) % snap
                base_time = base_time + timezone.timedelta(minutes=add_min)
                base_time = base_time.replace(second=0, microsecond=0)

                for i, gc in enumerate(generated_clips):
                    clip_id_str = gc.get("clip_id")
                    if not clip_id_str:
                        continue
                    try:
                        clip_obj = Clip.objects.get(clip_id=clip_id_str)
                    except Exception:
                        continue

                    scheduled_time = base_time + timezone.timedelta(minutes=60 * i)

                    Schedule.objects.create(
                        clip=clip_obj,
                        user_id=getattr(video, "user_id", None) or (job.user_id if job else None),
                        platform=auto_platform,
                        scheduled_time=scheduled_time,
                        status="scheduled",
                    )
                    created += 1

                logger.info(f"[clip_gen] Auto-schedule enabled: created {created} schedules")
            except Exception as e:
                logger.warning(f"[clip_gen] Auto-schedule failed: {e}")

        video.last_successful_step = "rendering"
        video.status = "done"
        video.current_step = "done"
        video.completed_at = timezone.now()
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "done",
            progress=100,
            current_step="done"
        )

        return {
            "video_id": str(video.video_id),
            "status": "done",
            "clips_count": len(generated_clips),
            "failures_count": len(failures),
        }

    except Video.DoesNotExist:
        logger.error(f"[clip_gen] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[clip_gen] Error for video_id={video_id}: {e}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.error_message = str(e)[:500]
            video.save()

            _safe_update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="rendering"
            )

        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(
                f"[clip_gen] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                f"in {countdown}s"
            )
            raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e)[:500], "status": "failed"}


def _render_clip(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    crop_config: Optional[Dict[str, int]] = None,
    ass_file: Optional[str] = None,
) -> None:
    
    if end_time <= start_time:
        raise ValueError(f"Invalid timestamps: start={start_time} end={end_time}")
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    ffmpeg_path = _get_config("FFMPEG_PATH", "ffmpeg", str)
    ffmpeg_timeout_s = _get_config("FFMPEG_RENDER_TIMEOUT_SECONDS", DEFAULT_FFMPEG_TIMEOUT, int)
    target_height = _get_config("CLIP_RENDER_TARGET_HEIGHT", DEFAULT_TARGET_HEIGHT, int)
    crf = _get_config("CLIP_RENDER_CRF", DEFAULT_CRF, int)
    preset = _get_config("CLIP_RENDER_PRESET", DEFAULT_PRESET, str)
    audio_bitrate = _get_config("CLIP_RENDER_AUDIO_BITRATE", DEFAULT_AUDIO_BITRATE, str)

    target_height = int(max(0, min(target_height, 4320)))
    crf = int(max(0, min(crf, 51)))
    
    valid_presets = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
    if preset not in valid_presets:
        preset = DEFAULT_PRESET

    duration = end_time - start_time

    filter_chain: List[str] = []
    
    if crop_config:
        w = crop_config["width"]
        h = crop_config["height"]
        x = crop_config["x"]
        y = crop_config["y"]
        filter_chain.append(f"crop={w}:{h}:{x}:{y}")
        logger.debug(f"[render] Crop: {w}x{h} at ({x},{y})")

    if ass_file and os.path.exists(ass_file):
        clean_ass_path = ass_file.replace("\\", "/")
        
        escaped_path = clean_ass_path.replace(":", "\\:")
        
        filter_chain.append(f"ass='{escaped_path}'")
        logger.debug(f"[render] ASS: {ass_file}")
    elif ass_file:
        logger.warning(f"[render] ASS file not found: {ass_file}")

    if target_height and target_height > 0:
        filter_chain.append(f"scale=-2:{target_height}")
        logger.debug(f"[render] Scale: height={target_height}")

    vf_arg = ",".join(filter_chain) if filter_chain else None

    cmd = [
        ffmpeg_path,
        "-y",
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-i", input_path,
    ]

    if vf_arg:
        cmd.extend(["-vf", vf_arg])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        output_path
    ])

    logger.debug(f"[render] FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=ffmpeg_timeout_s,
        )
    except subprocess.CalledProcessError as e:
        error_msg = (e.stderr if e.stderr else str(e))[:500]
        logger.error(f"[render] FFmpeg failed: {error_msg}")
        raise RuntimeError(f"FFmpeg render failed: {error_msg}")
    except subprocess.TimeoutExpired:
        logger.error(f"[render] FFmpeg timeout after {ffmpeg_timeout_s}s")
        raise TimeoutError(f"FFmpeg timeout after {ffmpeg_timeout_s}s")

    if not os.path.exists(output_path):
        raise RuntimeError("FFmpeg completed but output file not created")
    
    output_size = os.path.getsize(output_path)
    if output_size <= 0:
        raise RuntimeError("FFmpeg created empty output file")
    
    logger.debug(f"[render] Success: {output_path} ({output_size} bytes)")