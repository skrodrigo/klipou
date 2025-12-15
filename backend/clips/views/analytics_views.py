"""
Views para analytics e estatísticas.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime, timedelta
from django.db import models

from ..models import Organization, Job, Clip, CreditTransaction
from ..services.analytics_service import AnalyticsService


@api_view(["GET"])
def get_organization_stats(request, organization_id):
    """
    Obtém estatísticas gerais de uma organização.
    
    Query params:
    - period: "day|week|month|year" (padrão: month)
    """
    try:
        period = request.query_params.get("period", "month")
        
        # Calcula data inicial baseada no período
        now = datetime.now()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "year":
            start_date = now - timedelta(days=365)
        else:  # month
            start_date = now - timedelta(days=30)
        
        org = Organization.objects.get(organization_id=organization_id)
        
        # Conta jobs
        total_jobs = Job.objects.filter(
            organization_id=organization_id,
            created_at__gte=start_date
        ).count()
        
        completed_jobs = Job.objects.filter(
            organization_id=organization_id,
            status="completed",
            created_at__gte=start_date
        ).count()
        
        failed_jobs = Job.objects.filter(
            organization_id=organization_id,
            status="failed",
            created_at__gte=start_date
        ).count()
        
        # Conta clips
        total_clips = Clip.objects.filter(
            video__organization_id=organization_id,
            created_at__gte=start_date
        ).count()
        
        # Créditos
        credits_used = CreditTransaction.objects.filter(
            organization_id=organization_id,
            type="consumption",
            created_at__gte=start_date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return Response(
            {
                "organization_id": str(organization_id),
                "period": period,
                "stats": {
                    "total_jobs": total_jobs,
                    "completed_jobs": completed_jobs,
                    "failed_jobs": failed_jobs,
                    "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                    "total_clips": total_clips,
                    "credits_used": credits_used,
                    "credits_available": org.credits_available,
                    "plan": org.plan,
                },
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


@api_view(["GET"])
def get_job_performance(request, organization_id):
    """
    Obtém performance de jobs de uma organização.
    
    Query params:
    - limit: número máximo de resultados (padrão 10)
    """
    try:
        limit = int(request.query_params.get("limit", 10))
        
        jobs = Job.objects.filter(
            organization_id=organization_id,
            status="completed"
        ).order_by("-completed_at")[:limit]
        
        job_data = []
        for job in jobs:
            # Calcula duração
            if job.completed_at and job.created_at:
                duration = (job.completed_at - job.created_at).total_seconds()
            else:
                duration = 0
            
            # Conta clips
            clip_count = Clip.objects.filter(job_id=job.job_id).count()
            
            job_data.append({
                "job_id": str(job.job_id),
                "status": job.status,
                "duration_seconds": duration,
                "clips_generated": clip_count,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            })
        
        return Response(
            {
                "organization_id": str(organization_id),
                "jobs": job_data,
                "total": len(job_data),
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_failure_analysis(request, organization_id):
    """
    Obtém análise de falhas de jobs.
    
    Query params:
    - limit: número máximo de resultados (padrão 10)
    """
    try:
        limit = int(request.query_params.get("limit", 10))
        
        failed_jobs = Job.objects.filter(
            organization_id=organization_id,
            status="failed"
        ).order_by("-created_at")[:limit]
        
        failure_data = []
        for job in failed_jobs:
            failure_data.append({
                "job_id": str(job.job_id),
                "error_code": job.error_code,
                "error_message": job.error_message,
                "last_step": job.last_successful_step,
                "retry_count": job.retry_count,
                "created_at": job.created_at.isoformat(),
            })
        
        return Response(
            {
                "organization_id": str(organization_id),
                "failures": failure_data,
                "total": len(failure_data),
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_credit_usage(request, organization_id):
    """
    Obtém histórico de uso de créditos.
    
    Query params:
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        
        transactions = CreditTransaction.objects.filter(
            organization_id=organization_id
        ).order_by("-created_at")[offset : offset + limit]
        
        transaction_data = []
        for t in transactions:
            transaction_data.append({
                "transaction_id": str(t.transaction_id),
                "amount": t.amount,
                "type": t.type,
                "reason": t.reason,
                "balance_after": t.balance_after,
                "created_at": t.created_at.isoformat(),
            })
        
        total_transactions = CreditTransaction.objects.filter(
            organization_id=organization_id
        ).count()
        
        return Response(
            {
                "organization_id": str(organization_id),
                "transactions": transaction_data,
                "total": total_transactions,
                "limit": limit,
                "offset": offset,
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_clip_performance(request, clip_id):
    """
    Obtém performance de um clip específico.
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)
        
        return Response(
            {
                "clip_id": str(clip.clip_id),
                "title": clip.title,
                "duration": clip.duration,
                "engagement_score": clip.engagement_score,
                "confidence_score": clip.confidence_score,
                "ratio": clip.ratio,
                "created_at": clip.created_at.isoformat(),
                "updated_at": clip.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
    
    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
