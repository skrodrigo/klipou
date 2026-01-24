import logging
from ..models import Job

logger = logging.getLogger(__name__)


def get_plan_tier(plan: str | None) -> str:
    p = (plan or "").strip().lower()
    return "business" if p == "business" else "starter"


def update_job_status(
    video_id: str,
    status: str,
    progress: int = None,
    current_step: str = None
) -> bool:

    try:
        update_fields = {
            "status": status,
        }

        if progress is not None:
            update_fields["progress"] = progress
        
        if current_step is not None:
            update_fields["current_step"] = current_step

        qs = Job.objects.filter(video_id=video_id).exclude(status__in=["done", "failed"]).order_by("-created_at")
        jobs = list(qs)

        if not jobs:
            # Fallback: if no active jobs exist, update the latest one (best-effort).
            job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
            if not job:
                logger.warning(f"[job_utils] Job não encontrado para video_id={video_id}")
                return False
            jobs = [job]

        for job in jobs:
            for k, v in update_fields.items():
                setattr(job, k, v)
            job.save(update_fields=list(update_fields.keys()))
            logger.debug(
                f"[job_utils] Job atualizado: job_id={job.job_id} video_id={video_id}, "
                f"status={status}, progress={progress}, current_step={current_step}"
            )

        return True

    except Exception as e:
        logger.error(
            f"[job_utils] Erro crítico ao atualizar job {video_id}: {e}",
            exc_info=True
        )
        return False
