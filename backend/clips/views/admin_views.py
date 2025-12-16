"""
Views administrativas para gerenciamento de jobs, créditos e troubleshooting.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone

from ..models import Job, Organization, CreditTransaction, Video
from ..tasks import download_video_task


@api_view(["POST"])
def reprocess_job(request, job_id):
    """
    Reprocessa um job a partir de uma etapa específica.
    
    Body:
    {
        "from_step": "downloading|normalizing|transcribing|analyzing|...",
        "admin_key": "secret_key"
    }
    
    Requer autenticação de admin.
    """
    try:
        # Valida admin key
        admin_key = request.data.get("admin_key")
        if not _validate_admin_key(admin_key):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        job = Job.objects.get(job_id=job_id)
        from_step = request.data.get("from_step", "downloading")

        # Reseta job para etapa anterior
        job.status = "queued"
        job.current_step = from_step
        job.retry_count = 0
        job.error_code = None
        job.error_message = None
        job.save()

        # Dispara task apropriada
        video = Video.objects.get(video_id=job.video_id)

        if from_step == "downloading":
            task = download_video_task.apply_async(
                args=[video.id],
                queue=f"video.download.{job.organization.plan}",
            )
        else:
            # TODO: Implementar para outras etapas
            return Response(
                {"error": f"Reprocessing from '{from_step}' not yet implemented"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.task_id = task.id
        job.save()

        return Response(
            {
                "job_id": str(job.job_id),
                "status": "queued",
                "from_step": from_step,
                "task_id": task.id,
            },
            status=status.HTTP_200_OK,
        )

    except Job.DoesNotExist:
        return Response(
            {"error": "Job not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def cancel_job(request, job_id):
    """
    Cancela um job em execução.
    
    Body:
    {
        "reason": "string",
        "admin_key": "secret_key"
    }
    
    Requer autenticação de admin.
    """
    try:
        # Valida admin key
        admin_key = request.data.get("admin_key")
        if not _validate_admin_key(admin_key):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        job = Job.objects.get(job_id=job_id)
        reason = request.data.get("reason", "Canceled by admin")

        # Marca como cancelado
        job.status = "failed"
        job.error_code = "CANCELED_BY_ADMIN"
        job.error_message = reason
        job.save()

        # Estorna créditos
        org = Organization.objects.get(organization_id=job.organization_id)
        org.credits_available += job.credits_consumed
        org.save()

        CreditTransaction.objects.create(
            organization_id=org.organization_id,
            job_id=job.job_id,
            amount=-job.credits_consumed,
            type="refund",
            reason=f"Cancelamento por admin: {reason}",
            balance_after=org.credits_available,
        )

        return Response(
            {
                "job_id": str(job.job_id),
                "status": "canceled",
                "credits_refunded": job.credits_consumed,
            },
            status=status.HTTP_200_OK,
        )

    except Job.DoesNotExist:
        return Response(
            {"error": "Job not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def adjust_credits(request, organization_id):
    """
    Ajusta créditos de uma organização (admin).
    
    Body:
    {
        "amount": 100,
        "reason": "Promotional credits",
        "admin_key": "secret_key"
    }
    
    Requer autenticação de admin.
    """
    try:
        # Valida admin key
        admin_key = request.data.get("admin_key")
        if not _validate_admin_key(admin_key):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        org = Organization.objects.get(organization_id=organization_id)
        amount = int(request.data.get("amount", 0))
        reason = request.data.get("reason", "Admin adjustment")

        # Ajusta créditos
        org.credits_available += amount
        org.save()

        # Registra transação
        CreditTransaction.objects.create(
            organization_id=org.organization_id,
            amount=-amount,  # Negativo = adição
            type="adjustment",
            reason=reason,
            balance_after=org.credits_available,
        )

        return Response(
            {
                "organization_id": str(org.organization_id),
                "amount_adjusted": amount,
                "credits_available": org.credits_available,
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_job_failures(request):
    """
    Lista jobs que falharam.
    
    Query params:
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    - error_code: filtering por código de erro
    - admin_key: secret_key
    
    Requer autenticação de admin.
    """
    try:
        # Valida admin key
        admin_key = request.query_params.get("admin_key")
        if not _validate_admin_key(admin_key):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        error_code_filter = request.query_params.get("error_code")
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        query = Job.objects.filter(status="failed").order_by("-created_at")

        if error_code_filter:
            query = query.filter(error_code=error_code_filter)

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
                        "organization_id": str(job.organization_id),
                        "status": job.status,
                        "current_step": job.current_step,
                        "error_code": job.error_code,
                        "error_message": job.error_message,
                        "retry_count": job.retry_count,
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


@api_view(["GET"])
def get_step_statistics(request):
    """
    Retorna estatísticas de falhas por etapa.
    
    Query params:
    - admin_key: secret_key
    
    Requer autenticação de admin.
    """
    try:
        # Valida admin key
        admin_key = request.query_params.get("admin_key")
        if not _validate_admin_key(admin_key):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        from django.db.models import Count

        # Agrupa falhas por etapa
        failures_by_step = (
            Job.objects.filter(status="failed")
            .values("current_step")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Agrupa falhas por código de erro
        failures_by_error = (
            Job.objects.filter(status="failed")
            .values("error_code")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response(
            {
                "failures_by_step": list(failures_by_step),
                "failures_by_error": list(failures_by_error),
                "total_failed_jobs": Job.objects.filter(status="failed").count(),
                "total_jobs": Job.objects.count(),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _validate_admin_key(admin_key: str) -> bool:
    """Valida chave de admin."""
    from django.conf import settings

    expected_key = getattr(settings, "ADMIN_API_KEY", None)
    return admin_key and admin_key == expected_key
