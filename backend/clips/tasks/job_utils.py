"""
Utilitários para atualizar status de jobs durante o processamento.
Usa QuerySet.update() para evitar race conditions e overhead de banco de dados.
"""

import logging
from django.utils import timezone
from ..models import Job

logger = logging.getLogger(__name__)


def update_job_status(
    video_id: str,
    status: str,
    progress: int = None,
    current_step: str = None
) -> bool:
    """
    Atualiza status do job de forma ATÔMICA e performática.
    
    Usa .update() para evitar:
    - Race conditions (múltiplos workers atualizando simultaneamente)
    - Overhead de carregar objeto inteiro na memória
    - Sobrescrita de campos não intencionais
    
    Args:
        video_id: UUID do vídeo
        status: Novo status do job
        progress: Progresso (0-100), opcional
        current_step: Etapa atual, opcional
    
    Returns:
        bool: True se job foi atualizado, False se não encontrado
    """
    try:
        # Prepara os campos que serão atualizados
        update_fields = {
            "status": status,
        }

        if progress is not None:
            update_fields["progress"] = progress
        
        if current_step is not None:
            update_fields["current_step"] = current_step

        # Executa UPDATE direto no banco (Atomic, 1 query SQL)
        # Retorna número de linhas afetadas (0 se não achou, 1 se achou)
        affected = Job.objects.filter(video_id=video_id).update(**update_fields)
        
        if affected == 0:
            logger.warning(f"[job_utils] Job não encontrado para video_id={video_id}")
            return False
        
        logger.debug(
            f"[job_utils] Job atualizado: video_id={video_id}, "
            f"status={status}, progress={progress}"
        )
        return True

    except Exception as e:
        logger.error(
            f"[job_utils] Erro crítico ao atualizar job {video_id}: {e}",
            exc_info=True
        )
        return False
