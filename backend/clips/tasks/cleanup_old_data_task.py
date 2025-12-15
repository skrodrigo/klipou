"""
Task para limpeza de dados antigos.
Cron job executado diariamente.
Marca recursos como deletados (soft delete) conforme políticas de retenção.
"""

from datetime import datetime, timedelta
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import Video, Clip, Transcript, Job


@shared_task
def cleanup_old_data_task() -> dict:
    """
    Limpeza automática de dados antigos via soft delete.
    
    Políticas de Retenção:
    - Vídeo original: 30 dias (soft delete após 30 dias)
    - Clips gerados: Indefinido (manter enquanto plano ativo)
    - Legendas (ASS): Indefinido (manter para reutilização)
    - Transcrição: Indefinido (manter para análise futura)
    - Jobs falhos: 7 dias (soft delete após 7 dias)
    - Logs: 30 dias (arquivar após 30 dias)
    - Dados após cancelamento: 90 dias (soft delete 3 meses após cancelamento)
    
    Regras:
    - Dados nunca são removidos do banco (apenas marcados como deletados)
    - Hard delete NUNCA ocorre (apenas soft delete permanente)
    - Recuperação possível por admin se necessário
    """
    try:
        now = timezone.now()
        cleaned_count = 0
        failed_count = 0

        # 1. Soft delete de vídeos originais com mais de 30 dias
        cleaned_count += _cleanup_old_videos(now)

        # 2. Soft delete de jobs falhos com mais de 7 dias
        cleaned_count += _cleanup_failed_jobs(now)

        # 3. Soft delete de dados após cancelamento (90 dias)
        cleaned_count += _cleanup_canceled_subscriptions(now)

        return {
            "status": "completed",
            "cleaned_count": cleaned_count,
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": timezone.now().isoformat(),
        }


def _cleanup_old_videos(now: datetime) -> int:
    """Soft delete de vídeos originais com mais de 30 dias."""
    thirty_days_ago = now - timedelta(days=30)

    # Encontra vídeos criados há mais de 30 dias que ainda não foram deletados
    old_videos = Video.objects.filter(
        created_at__lt=thirty_days_ago,
        is_deleted=False,  # Ainda não foi deletado
        status__in=["completed", "failed"],  # Apenas vídeos processados
    )

    count = 0
    for video in old_videos:
        try:
            # Marca como deletado (soft delete)
            video.is_deleted = True
            video.deleted_at = now
            video.save()

            # Opcionalmente, deleta arquivo do R2 (pode ser comentado para manter backup)
            # _delete_from_r2(video.storage_path)

            count += 1
        except Exception as e:
            print(f"Erro ao deletar vídeo {video.id}: {e}")
            continue

    return count


def _cleanup_failed_jobs(now: datetime) -> int:
    """Soft delete de jobs falhos com mais de 7 dias."""
    seven_days_ago = now - timedelta(days=7)

    # Encontra jobs falhos criados há mais de 7 dias
    failed_jobs = Job.objects.filter(
        created_at__lt=seven_days_ago,
        is_deleted=False,
        status="failed",
    )

    count = 0
    for job in failed_jobs:
        try:
            # Marca como deletado (soft delete)
            job.is_deleted = True
            job.deleted_at = now
            job.save()

            count += 1
        except Exception as e:
            print(f"Erro ao deletar job {job.id}: {e}")
            continue

    return count


def _cleanup_canceled_subscriptions(now: datetime) -> int:
    """Soft delete de dados após cancelamento (90 dias)."""
    ninety_days_ago = now - timedelta(days=90)

    # Encontra organizações com cancelamento há mais de 90 dias
    from ..models import Organization, Subscription

    canceled_subs = Subscription.objects.filter(
        status="canceled",
        canceled_at__lt=ninety_days_ago,
    )

    count = 0
    for sub in canceled_subs:
        try:
            org = sub.organization

            # Soft delete de todos os vídeos da organização
            videos = Video.objects.filter(
                organization_id=org.id,
                is_deleted=False,
            )

            for video in videos:
                video.is_deleted = True
                video.deleted_at = now
                video.save()
                count += 1

            # Soft delete de todos os clips da organização
            clips = Clip.objects.filter(
                video__organization_id=org.id,
                is_deleted=False,
            )

            for clip in clips:
                clip.is_deleted = True
                clip.deleted_at = now
                clip.save()
                count += 1

        except Exception as e:
            print(f"Erro ao deletar dados da organização {org.id}: {e}")
            continue

    return count


def _delete_from_r2(storage_path: str) -> None:
    """Deleta arquivo do R2 (opcional, pode ser comentado)."""
    try:
        from .storage_service import R2StorageService
        storage = R2StorageService()
        storage.delete_file(storage_path)
    except Exception as e:
        print(f"Aviso: Falha ao deletar arquivo do R2: {e}")
