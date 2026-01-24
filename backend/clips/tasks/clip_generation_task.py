import logging
import os
import uuid
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import Video, Clip, Transcript, Organization
from .job_utils import update_job_status
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, acks_late=False)
def clip_generation_task(self, video_id: str) -> dict:
    try:
        logger.info(f"Iniciando renderização final para video_id: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "rendering"
        video.current_step = "rendering"
        video.save()

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        caption_files = transcript.caption_files or []
        reframe_data = transcript.reframe_data or {}
        
        crop_config = reframe_data.get("crops", {}).get("9:16")
        
        if not selected_clips:
            raise Exception("Nenhum clip para renderizar")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        input_path = os.path.join(output_dir, "video_normalized.mp4")
        if not os.path.exists(input_path):
            raise Exception("Vídeo normalizado não encontrado")

        storage = R2StorageService()
        generated_clips = []

        total_clips = len(selected_clips)

        render_jobs = []
        for idx, clip in enumerate(selected_clips):
            clip_uuid = uuid.uuid4()
            start_time = float(clip.get("start_time", 0))
            end_time = float(clip.get("end_time", 0))

            try:
                if video.duration and float(video.duration) > 0:
                    end_time = min(end_time + 1.0, float(video.duration))
                else:
                    end_time = end_time + 1.0
            except Exception:
                end_time = end_time + 1.0

            hook_title = clip.get("title") or clip.get("hook_title", f"Clip {idx + 1}")
            matched_caption = next((c for c in caption_files if c.get("index") == idx), None)
            ass_file = matched_caption.get("ass_file") if matched_caption else None

            clip_filename = f"clip_{clip_uuid}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)

            render_jobs.append(
                {
                    "idx": idx,
                    "clip_uuid": clip_uuid,
                    "clip_path": clip_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "hook_title": hook_title,
                    "ass_file": ass_file,
                    "transcript_text": clip.get("text", ""),
                    "score_0_100": float(clip.get("score", 0) or 0),
                }
            )

        max_workers = int(
            getattr(settings, "CLIP_RENDER_MAX_WORKERS", None)
            or max(1, min(4, (os.cpu_count() or 2)))
        )

        completed = 0
        failures: list[dict] = []

        update_job_status(str(video.video_id), "rendering", progress=85, current_step="rendering")

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
                    failures.append({"idx": job["idx"], "error": str(e)})
                    logger.error(f"Falha ao renderizar clip idx={job['idx']}: {e}")
                    if os.path.exists(job["clip_path"]):
                        try:
                            os.remove(job["clip_path"])
                        except Exception:
                            pass
                    continue

                completed += 1
                progress = 85 + int((completed / total_clips) * 10)
                update_job_status(
                    str(video.video_id),
                    "rendering",
                    progress=progress,
                    current_step=f"rendering_clip_{completed}/{total_clips}",
                )

                clip_path = job["clip_path"]
                file_size = os.path.getsize(clip_path)
                clip_storage_path = storage.upload_clip(
                    file_path=clip_path,
                    organization_id=str(video.organization_id),
                    video_id=str(video.video_id),
                    clip_id=str(job["clip_uuid"]),
                )

                engagement_score = round(job["score_0_100"] / 10.0, 2)

                Clip.objects.create(
                    clip_id=job["clip_uuid"],
                    video=video,
                    title=job["hook_title"],
                    start_time=job["start_time"],
                    end_time=job["end_time"],
                    duration=job["end_time"] - job["start_time"],
                    storage_path=clip_storage_path,
                    file_size=file_size,
                    transcript=job["transcript_text"],
                    engagement_score=engagement_score,
                    confidence_score=0,
                )

                generated_clips.append(
                    {
                        "clip_id": str(job["clip_uuid"]),
                        "url": clip_storage_path,
                    }
                )

                if os.path.exists(clip_path):
                    os.remove(clip_path)

        if not generated_clips:
            raise Exception(f"Nenhum clip renderizado com sucesso. failures={failures[:3]}")

        video.last_successful_step = "rendering"
        video.status = "done"
        video.current_step = "done"
        video.completed_at = timezone.now()
        video.save()
        
        update_job_status(str(video.video_id), "done", progress=100, current_step="done")

        return {
            "video_id": str(video.video_id),
            "status": "done",
            "clips_count": len(generated_clips),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro na renderização final: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

            update_job_status(str(video.video_id), "failed", progress=100, current_step="rendering")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _render_clip(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    crop_config: dict = None,
    ass_file: str = None,
) -> None:
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    duration = end_time - start_time

    target_height = int(getattr(settings, "CLIP_RENDER_TARGET_HEIGHT", 720) or 720)

    filter_chain = []
    
    if crop_config:
        w = crop_config.get("width")
        h = crop_config.get("height")
        x = crop_config.get("x")
        y = crop_config.get("y")
        filter_chain.append(f"crop={w}:{h}:{x}:{y}")

    if ass_file and os.path.exists(ass_file):
        clean_ass_path = ass_file.replace("\\", "/").replace(":", "\\:")
        filter_chain.append(f"ass='{clean_ass_path}'")

    if target_height and int(target_height) > 0:
        filter_chain.append(f"scale=-2:{int(target_height)}")

    vf_arg = ",".join(filter_chain)

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
        "-preset", "medium",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ])

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"FFmpeg Render falhou: {error_msg}")
        raise Exception(f"Falha no render do clip: {error_msg}")

    if not os.path.exists(output_path):
        raise Exception("Arquivo final não foi criado pelo FFmpeg")
