"""
Task para limpeza de dados e arquivos antigos.
Cron job executado diariamente.
Estratégia: Hard Delete de arquivos (economia) + Soft Delete de registros (auditoria).
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone

from ..models import Video, Clip, Job, Subscription
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_data_task() -> dict:
    """
    Limpeza de dados e arquivos antigos com otimizações de performance e custo.
    
    Estratégia de Custo:
    - Vídeos Originais (>30 dias): Hard Delete do arquivo R2 + Soft Delete no DB.
    - Jobs Falhos (>7 dias): Bulk Update no DB (1 query em vez de N).
    - Cancelados (>90 dias): Soft Delete em cascata com limpeza de arquivos.
    
    Performance:
    - Iterator com chunk_size=100: Evita carregar 50k objetos na RAM.
    - Bulk Update: Transforma loops em operações de milissegundos.
    - Logging: Rastreamento profissional de operações.
    """
    try:
        now = timezone.now()
        stats = {
            "videos_cleaned": 0,
            "jobs_cleaned": 0,
            "canceled_data_cleaned": 0,
        }

        logger.info("[CLEANUP] Iniciando limpeza de dados antigos")

        # 1. Vídeos Originais (Iterativo pois envolve deleção de arquivo)
        stats["videos_cleaned"] = _cleanup_old_videos(now)

        # 2. Jobs Falhos (Bulk Update - Muito mais rápido)
        stats["jobs_cleaned"] = _cleanup_failed_jobs(now)

        # 3. Cancelamentos (Cascata com limpeza de arquivos)
        stats["canceled_data_cleaned"] = _cleanup_canceled_subscriptions(now)

        logger.info(f"[CLEANUP] Limpeza concluída: {stats}")
        return {
            "status": "completed",
            "timestamp": now.isoformat(),
            **stats
        }

    except Exception as e:
        logger.error(f"[CLEANUP] Erro fatal na task de limpeza: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": timezone.now().isoformat()
        }


def _cleanup_old_videos(now: datetime) -> int:
    """
    Remove vídeos originais antigos para economizar armazenamento.
    
    Estratégia:
    1. Hard Delete: Apaga arquivo pesado do R2 (economia real).
    2. Soft Delete: Marca registro no banco como deletado (auditoria).
    
    Performance: Usa .iterator(chunk_size=100) para não estourar RAM.
    """
    thirty_days_ago = now - timedelta(days=30)
    
    logger.info("[CLEANUP-VIDEOS] Iniciando limpeza de vídeos com >30 dias")
    
    # Filtra vídeos aptos para limpeza
    # .iterator() evita carregar 10k objetos na memória RAM de uma vez
    old_videos_qs = Video.objects.filter(
        created_at__lt=thirty_days_ago,
        is_deleted=False
    ).exclude(
        # Não deletar se ainda estiver processando (improvável, mas seguro)
        status__in=["processing", "uploading"]
    ).iterator(chunk_size=100)

    storage = R2StorageService()
    count = 0
    errors = 0

    for video in old_videos_qs:
        try:
            # 1. Hard Delete: Apaga arquivo físico do R2 (Onde está o custo real)
            if video.storage_path:
                try:
                    storage.delete_file(video.storage_path)
                    logger.debug(f"[CLEANUP-VIDEOS] Arquivo R2 deletado: {video.storage_path}")
                except Exception as e:
                    logger.warning(
                        f"[CLEANUP-VIDEOS] Falha ao apagar arquivo R2 "
                        f"do vídeo {video.video_id}: {e}"
                    )
                    errors += 1

            # 2. Soft Delete: Marca no banco (auditoria + recuperação possível)
            video.is_deleted = True
            video.deleted_at = now
            video.storage_path = None  # Remove referência para indicar arquivo sumiu
            video.save(update_fields=["is_deleted", "deleted_at", "storage_path"])
            
            count += 1
            
        except Exception as e:
            logger.error(f"[CLEANUP-VIDEOS] Erro ao limpar vídeo {video.video_id}: {e}")
            errors += 1
            continue

    logger.info(
        f"[CLEANUP-VIDEOS] Concluído: {count} vídeos limpos, {errors} erros"
    )
    return count


def _cleanup_failed_jobs(now: datetime) -> int:
    """
    Marca jobs antigos como deletados.
    
    Performance: Usa BULK UPDATE para performance (1 query em vez de N).
    Isso transforma um loop que demoraria minutos em uma operação de milissegundos.
    """
    seven_days_ago = now - timedelta(days=7)

    logger.info("[CLEANUP-JOBS] Iniciando limpeza de jobs com >7 dias")

    # .update() retorna o número de linhas afetadas
    # Muito mais rápido que um loop com .save()
    affected_rows = Job.objects.filter(
        created_at__lt=seven_days_ago,
        is_deleted=False,
        status__in=["failed"]
    ).update(
        is_deleted=True,
        deleted_at=now
    )

    logger.info(f"[CLEANUP-JOBS] {affected_rows} jobs marcados como deletados")
    return affected_rows


def _cleanup_canceled_subscriptions(now: datetime) -> int:
    """
    Limpa dados de clientes que cancelaram há mais de 90 dias.
    
    Estratégia:
    1. Busca IDs de orgs canceladas.
    2. Itera clips para apagar arquivos R2 (economia).
    3. Bulk update de vídeos (performance).
    """
    ninety_days_ago = now - timedelta(days=90)
    
    logger.info("[CLEANUP-CANCELED] Iniciando limpeza de dados cancelados >90 dias")
    
    # Busca IDs de orgs com cancelamento antigo
    canceled_org_ids = list(
        Subscription.objects.filter(
            status="canceled",
            canceled_at__lt=ninety_days_ago
        ).values_list('organization_id', flat=True)
    )
    
    if not canceled_org_ids:
        logger.info("[CLEANUP-CANCELED] Nenhuma organização para limpar")
        return 0

    logger.info(f"[CLEANUP-CANCELED] {len(canceled_org_ids)} orgs para limpar")

    count = 0
    storage = R2StorageService()

    # 1. Limpa Clips (Arquivos + DB)
    # Usa select_related para otimizar SQL
    clips_to_clean = Clip.objects.filter(
        video__organization_id__in=canceled_org_ids,
        is_deleted=False
    ).select_related('video').iterator(chunk_size=100)

    for clip in clips_to_clean:
        try:
            # Hard Delete do arquivo
            if clip.storage_path:
                try:
                    storage.delete_file(clip.storage_path)
                except Exception as e:
                    logger.warning(
                        f"[CLEANUP-CANCELED] Falha ao apagar clip {clip.clip_id}: {e}"
                    )
            
            # Soft Delete do registro
            clip.is_deleted = True
            clip.deleted_at = now
            clip.storage_path = None
            clip.save(update_fields=["is_deleted", "deleted_at", "storage_path"])
            count += 1
            
        except Exception as e:
            logger.error(f"[CLEANUP-CANCELED] Erro ao limpar clip {clip.clip_id}: {e}")
            continue

    # 2. Marca Vídeos Restantes como deletados (Bulk Update - Rápido)
    videos_affected = Video.objects.filter(
        organization_id__in=canceled_org_ids,
        is_deleted=False
    ).update(
        is_deleted=True,
        deleted_at=now
    )

    count += videos_affected
    logger.info(
        f"[CLEANUP-CANCELED] Concluído: {count} recursos limpos "
        f"({videos_affected} vídeos)"
    )
    return count
