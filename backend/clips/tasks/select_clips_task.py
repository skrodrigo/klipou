import logging
from celery import shared_task

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def select_clips_task(self, video_id: str) -> dict:
    try:
        logger.info(f"Iniciando seleção de clips para video_id: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "selecting"
        video.current_step = "selecting"
        video.save()

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not candidates:
            raise Exception("Nenhum candidato de clip encontrado na análise")

        config = {
            "max_duration": 90,
            "min_duration": 15,
            "target_clips": 5 if org.plan in ["pro", "business"] else 3,
            "min_score": 40,
        }

        selected_clips = _process_selection(candidates, config)

        if not selected_clips:
            logger.warning("Nenhum clip passou nos critérios. Relaxando regras...")
            config["min_score"] = 10
            selected_clips = _process_selection(candidates, config)
            
            if not selected_clips:
                raise Exception("Não foi possível selecionar nenhum clip válido")

        transcript.selected_clips = selected_clips
        transcript.save()

        video.last_successful_step = "selecting"
        video.status = "reframing"
        video.current_step = "reframing"
        video.save()
        
        update_job_status(str(video.video_id), "reframing", progress=70, current_step="reframing")

        from .reframe_video_task import reframe_video_task
        reframe_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.reframe.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "selected_count": len(selected_clips),
            "top_score": selected_clips[0]["score"] if selected_clips else 0
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro na seleção {video_id}: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _process_selection(candidates: list, config: dict) -> list:
    valid_candidates = []

    for c in candidates:
        start = float(c.get("start_time", 0))
        end = float(c.get("end_time", 0))
        duration = end - start
        
        score = c.get("adjusted_engagement_score")
        if score is None:
            score = int(c.get("engagement_score", 0)) * 10
        
        if duration < config["min_duration"] or duration > config["max_duration"]:
            continue
            
        if score < config["min_score"]:
            continue

        valid_candidates.append({
            "start_time": start,
            "end_time": end,
            "duration": duration,
            "text": c.get("text", ""),
            "title": c.get("hook_title", "Viral Clip"),
            "score": score,
            "reasoning": c.get("reasoning", "")
        })

    valid_candidates.sort(key=lambda x: x["score"], reverse=True)

    final_selection = []
    
    for candidate in valid_candidates:
        if len(final_selection) >= config["target_clips"]:
            break
            
        is_overlapping = False
        for selected in final_selection:
            if _check_overlap(candidate, selected):
                is_overlapping = True
                break
        
        if not is_overlapping:
            final_selection.append(candidate)
            
    return final_selection


def _check_overlap(clip_a: dict, clip_b: dict, threshold: float = 2.0) -> bool:
    start_a, end_a = clip_a["start_time"], clip_a["end_time"]
    start_b, end_b = clip_b["start_time"], clip_b["end_time"]

    intersection_start = max(start_a, start_b)
    intersection_end = min(end_a, end_b)
    
    if intersection_end < intersection_start:
        return False

    intersection_duration = intersection_end - intersection_start
    
    if intersection_duration > threshold:
        return True
        
    return False
