"""
Serviço de analytics e métricas.
"""

from django.db.models import Count, Avg, Sum
from django.utils import timezone
from datetime import timedelta

from ..models import Job, Video, Clip, CreditTransaction


class AnalyticsService:
    """Serviço para coleta e análise de métricas."""

    @staticmethod
    def get_organization_stats(organization_id) -> dict:
        """Obtém estatísticas gerais de uma organização."""
        try:
            # Jobs
            total_jobs = Job.objects.filter(organization_id=organization_id).count()
            completed_jobs = Job.objects.filter(
                organization_id=organization_id,
                status="done"
            ).count()
            failed_jobs = Job.objects.filter(
                organization_id=organization_id,
                status="failed"
            ).count()

            # Vídeos
            total_videos = Video.objects.filter(organization_id=organization_id).count()

            # Clips
            total_clips = Clip.objects.filter(
                video__organization_id=organization_id
            ).count()

            # Créditos
            total_consumed = CreditTransaction.objects.filter(
                organization_id=organization_id,
                type="consumption"
            ).aggregate(Sum("amount"))["amount__sum"] or 0

            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                "total_videos": total_videos,
                "total_clips": total_clips,
                "total_credits_consumed": total_consumed,
            }
        except Exception as e:
            raise Exception(f"Erro ao obter estatísticas: {e}")

    @staticmethod
    def get_job_performance(organization_id) -> dict:
        """Obtém performance de jobs (tempo médio por etapa)."""
        try:
            from django.db.models import F, ExpressionWrapper, DurationField
            from django.db.models.functions import Extract

            # Tempo médio de processamento
            jobs = Job.objects.filter(
                organization_id=organization_id,
                status="done",
                completed_at__isnull=False,
            )

            if not jobs.exists():
                return {"average_processing_time": 0, "jobs_analyzed": 0}

            total_time = sum([
                (job.completed_at - job.created_at).total_seconds()
                for job in jobs
            ])

            average_time = total_time / jobs.count()

            return {
                "average_processing_time_seconds": int(average_time),
                "jobs_analyzed": jobs.count(),
            }
        except Exception as e:
            raise Exception(f"Erro ao obter performance: {e}")

    @staticmethod
    def get_failure_analysis(organization_id) -> dict:
        """Analisa falhas de jobs."""
        try:
            failed_jobs = Job.objects.filter(
                organization_id=organization_id,
                status="failed"
            )

            # Agrupa por etapa
            by_step = failed_jobs.values("current_step").annotate(
                count=Count("id")
            ).order_by("-count")

            # Agrupa por código de erro
            by_error = failed_jobs.values("error_code").annotate(
                count=Count("id")
            ).order_by("-count")

            return {
                "total_failed": failed_jobs.count(),
                "failures_by_step": list(by_step),
                "failures_by_error": list(by_error),
            }
        except Exception as e:
            raise Exception(f"Erro ao analisar falhas: {e}")

    @staticmethod
    def get_credit_usage(organization_id, days: int = 30) -> dict:
        """Obtém histórico de uso de créditos."""
        try:
            start_date = timezone.now() - timedelta(days=days)

            transactions = CreditTransaction.objects.filter(
                organization_id=organization_id,
                created_at__gte=start_date,
            ).order_by("created_at")

            # Agrupa por tipo
            by_type = transactions.values("type").annotate(
                total=Sum("amount")
            )

            # Agrupa por dia
            by_day = transactions.values("created_at__date").annotate(
                total=Sum("amount")
            ).order_by("created_at__date")

            return {
                "period_days": days,
                "total_consumed": sum([t["total"] for t in by_type if t["type"] == "consumption"]),
                "total_refunded": sum([t["total"] for t in by_type if t["type"] == "refund"]),
                "total_purchased": sum([t["total"] for t in by_type if t["type"] == "purchase"]),
                "by_type": list(by_type),
                "by_day": list(by_day),
            }
        except Exception as e:
            raise Exception(f"Erro ao obter uso de créditos: {e}")

    @staticmethod
    def get_clip_quality_metrics(organization_id) -> dict:
        """Obtém métricas de qualidade de clips."""
        try:
            clips = Clip.objects.filter(
                video__organization_id=organization_id
            )

            if not clips.exists():
                return {
                    "total_clips": 0,
                    "average_engagement_score": 0,
                    "average_confidence_score": 0,
                }

            avg_engagement = clips.aggregate(
                avg=Avg("engagement_score")
            )["avg"] or 0

            avg_confidence = clips.aggregate(
                avg=Avg("confidence_score")
            )["avg"] or 0

            # Distribuição por proporção
            by_ratio = clips.values("ratio").annotate(
                count=Count("id")
            )

            return {
                "total_clips": clips.count(),
                "average_engagement_score": round(avg_engagement, 2),
                "average_confidence_score": round(avg_confidence, 2),
                "by_ratio": list(by_ratio),
            }
        except Exception as e:
            raise Exception(f"Erro ao obter métricas de clips: {e}")

    @staticmethod
    def get_system_health() -> dict:
        """Obtém saúde geral do sistema."""
        try:
            # Jobs em execução
            running_jobs = Job.objects.filter(status__in=["queued", "downloading", "normalizing", "transcribing", "analyzing", "embedding", "selecting", "reframing", "clipping", "captioning"]).count()

            # Taxa de sucesso global
            total_jobs = Job.objects.count()
            successful_jobs = Job.objects.filter(status="done").count()
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0

            # Falhas recentes (últimas 24h)
            recent_failures = Job.objects.filter(
                status="failed",
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()

            return {
                "running_jobs": running_jobs,
                "total_jobs": total_jobs,
                "successful_jobs": successful_jobs,
                "success_rate": round(success_rate, 2),
                "recent_failures_24h": recent_failures,
                "system_status": "healthy" if success_rate > 90 else "degraded" if success_rate > 70 else "critical",
            }
        except Exception as e:
            raise Exception(f"Erro ao obter saúde do sistema: {e}")
