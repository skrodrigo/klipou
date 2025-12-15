"""
Views para admin dashboard com métricas e controles.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, timedelta
from django.db import models

from ..models import Job, Organization, CreditTransaction


@api_view(["GET"])
def admin_dashboard(request):
    """
    Dashboard admin com métricas gerais do sistema.
    
    Query params:
    - period: "day|week|month" (padrão: day)
    """
    try:
        period = request.query_params.get("period", "day")
        
        # Calcula data inicial
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # day
            start_date = now - timedelta(days=1)
        
        # Métricas de jobs
        total_jobs = Job.objects.filter(created_at__gte=start_date).count()
        completed_jobs = Job.objects.filter(
            status="completed",
            created_at__gte=start_date
        ).count()
        failed_jobs = Job.objects.filter(
            status="failed",
            created_at__gte=start_date
        ).count()
        
        success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        # Métricas de organizações
        total_orgs = Organization.objects.count()
        active_orgs = Organization.objects.filter(
            subscription__status="active"
        ).count()
        
        # Métricas de créditos
        total_credits_consumed = CreditTransaction.objects.filter(
            type="consumption",
            created_at__gte=start_date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        total_credits_refunded = CreditTransaction.objects.filter(
            type="refund",
            created_at__gte=start_date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        # Jobs em processamento
        processing_jobs = Job.objects.filter(
            status__in=["queued", "downloading", "normalizing", "transcribing", "analyzing", "embedding", "selecting", "reframing", "clipping", "captioning"]
        ).count()
        
        return Response(
            {
                "period": period,
                "metrics": {
                    "jobs": {
                        "total": total_jobs,
                        "completed": completed_jobs,
                        "failed": failed_jobs,
                        "processing": processing_jobs,
                        "success_rate": round(success_rate, 2),
                    },
                    "organizations": {
                        "total": total_orgs,
                        "active": active_orgs,
                    },
                    "credits": {
                        "consumed": total_credits_consumed,
                        "refunded": total_credits_refunded,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def system_health(request):
    """
    Health check do sistema.
    """
    try:
        # Verifica jobs em processamento
        processing_jobs = Job.objects.filter(
            status__in=["queued", "downloading", "normalizing", "transcribing", "analyzing", "embedding", "selecting", "reframing", "clipping", "captioning"]
        ).count()
        
        # Verifica jobs com erro
        failed_jobs_24h = Job.objects.filter(
            status="failed",
            created_at__gte=datetime.now() - timedelta(hours=24)
        ).count()
        
        # Taxa de falha
        total_jobs_24h = Job.objects.filter(
            created_at__gte=datetime.now() - timedelta(hours=24)
        ).count()
        
        failure_rate = (failed_jobs_24h / total_jobs_24h * 100) if total_jobs_24h > 0 else 0
        
        # Status geral
        health_status = "healthy"
        if failure_rate > 10:
            health_status = "warning"
        if failure_rate > 25:
            health_status = "critical"
        
        return Response(
            {
                "status": health_status,
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "processing_jobs": processing_jobs,
                    "failed_jobs_24h": failed_jobs_24h,
                    "total_jobs_24h": total_jobs_24h,
                    "failure_rate": round(failure_rate, 2),
                },
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def block_organization(request, organization_id):
    """
    Bloqueia uma organização (impede novos jobs).
    
    Body:
    {
        "reason": "Motivo do bloqueio"
    }
    """
    try:
        reason = request.data.get("reason", "Bloqueado por admin")
        
        org = Organization.objects.get(organization_id=organization_id)
        
        # TODO: Implementar bloqueio (adicionar campo is_blocked ao Organization)
        
        return Response(
            {
                "organization_id": str(organization_id),
                "status": "blocked",
                "reason": reason,
            },
            status=status.HTTP_200_OK,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def unblock_organization(request, organization_id):
    """
    Desbloqueia uma organização.
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)
        
        # TODO: Implementar desbloqueio
        
        return Response(
            {
                "organization_id": str(organization_id),
                "status": "unblocked",
            },
            status=status.HTTP_200_OK,
        )
    
    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
