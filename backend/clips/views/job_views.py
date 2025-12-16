"""
Views para gerenciamento de jobs de processamento de vídeo.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import StreamingHttpResponse
import json
import time

from ..models import Video, Job, CreditTransaction
from ..tasks import download_video_task
from ..decorators import require_credits, rate_limit


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@require_credits
@rate_limit(requests_per_hour=10, requests_per_minute=100)
def create_job(request):
    """
    Cria um novo job de processamento de vídeo.
    
    Validações:
    - Usuário autenticado
    - Créditos suficientes
    - Rate limiting
    - Vídeo existe
    
    Body:
    {
        "video_id": "uuid",
        "organization_id": "uuid",
        "configuration": {
            "language": "pt-BR",
            "target_ratios": ["9:16", "1:1", "16:9"],
            "max_clip_duration": 60,
            "num_clips": 5,
            "auto_schedule": false
        }
    }
    """
    try:
        # Obtém user_id do usuário autenticado
        user_id = request.user.user_id
        
        video_id = request.data.get("video_id")
        organization_id = request.data.get("organization_id")
        configuration = request.data.get("configuration", {})

        # Obtém dados do decorator
        credits_needed = request.credits_needed
        org = request.organization

        # Valida vídeo
        video = Video.objects.get(video_id=video_id)

        # Deduz créditos
        org.credits_available -= credits_needed
        org.save()

        # Registra transação
        CreditTransaction.objects.create(
            organization_id=organization_id,
            amount=credits_needed,
            type="consumption",
            reason=f"Processamento de vídeo - {video.title}",
            balance_after=org.credits_available,
        )

        # Cria job
        job = Job.objects.create(
            user_id=user_id,
            organization_id=organization_id,
            video_id=video_id,
            status="queued",
            configuration=configuration,
            credits_consumed=credits_needed,
        )

        # Dispara primeira task
        task = download_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.download.{org.plan}",
        )

        job.task_id = task.id
        job.save()

        return Response(
            {
                "job_id": str(job.job_id),
                "status": "queued",
                "task_id": task.id,
                "credits_consumed": credits_needed,
                "credits_remaining": org.credits_available,
            },
            status=status.HTTP_201_CREATED,
        )

    except Video.DoesNotExist:
        return Response(
            {"error": "Video not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_job_status(request, job_id):
    """
    Obtém status de um job.
    
    Response:
    {
        "job_id": "uuid",
        "status": "downloading",
        "progress": 25,
        "current_step": "downloading",
        "error_code": null,
        "error_message": null
    }
    """
    try:
        job = Job.objects.get(job_id=job_id)

        return Response(
            {
                "job_id": str(job.job_id),
                "status": job.status,
                "progress": job.progress,
                "current_step": job.current_step,
                "last_successful_step": job.last_successful_step,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            },
            status=status.HTTP_200_OK,
        )

    except Job.DoesNotExist:
        return Response(
            {"error": "Job not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
def list_jobs(request, organization_id):
    """
    Lista todos os jobs de uma organização.
    
    Query params:
    - status: filtering por status
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        status_filter = request.query_params.get("status")
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        query = Job.objects.filter(organization_id=organization_id).order_by("-created_at")

        if status_filter:
            query = query.filter(status=status_filter)

        total = query.count()
        jobs = query[offset : offset + limit]

        return Response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "jobs": [
                    {
                        "job_id": str(job.job_id),
                        "video_id": str(job.video_id),
                        "status": job.status,
                        "progress": job.progress,
                        "created_at": job.created_at.isoformat(),
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    }
                    for job in jobs
                ],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


def sse_job_status(request, job_id):
    """
    Server-Sent Events (SSE) para notificações em tempo real do progresso do job.
    
    Cliente se conecta e recebe atualizações em tempo real conforme o job progride.
    """
    try:
        job = Job.objects.get(job_id=job_id)
    except Job.DoesNotExist:
        return StreamingHttpResponse(
            [b"data: {\"error\": \"Job not found\"}\n\n"],
            content_type="text/event-stream",
            status=404,
        )

    def event_stream():
        """Generator que envia eventos SSE."""
        last_status = None
        last_progress = None
        reconnect_attempts = 0
        max_reconnect_time = 300  # 5 minutos

        while reconnect_attempts < max_reconnect_time:
            try:
                job.refresh_from_db()

                # Envia atualização se status ou progresso mudou
                if job.status != last_status or job.progress != last_progress:
                    event_data = {
                        "job_id": str(job.job_id),
                        "status": job.status,
                        "progress": job.progress,
                        "current_step": job.current_step,
                        "last_successful_step": job.last_successful_step,
                        "error_code": job.error_code,
                        "error_message": job.error_message,
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

                    last_status = job.status
                    last_progress = job.progress

                    # Se job completou ou falhou, encerra conexão
                    if job.status in ["done", "failed"]:
                        yield ": Connection closing\n\n"
                        break

                # Keepalive a cada 30 segundos
                yield ": keepalive\n\n"

                time.sleep(1)
                reconnect_attempts += 1

            except Exception as e:
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _get_plan(organization_id):
    """Obtém o plano da organização para roteamento de fila."""
    from ..models import Organization

    try:
        org = Organization.objects.get(organization_id=organization_id)
        return org.plan
    except Organization.DoesNotExist:
        return "starter"  # Padrão
