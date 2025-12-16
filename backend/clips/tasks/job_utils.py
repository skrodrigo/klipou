"""
Utilitários para atualizar status de jobs durante o processamento.
"""

from ..models import Job


def update_job_status(video_id: str, status: str, progress: int = None, current_step: str = None):
    """
    Atualiza o status de um job baseado no video_id.
    
    Args:
        video_id: UUID do vídeo
        status: Novo status do job
        progress: Progresso (0-100), opcional
        current_step: Etapa atual, opcional
    """
    try:
        # Procura job pelo video_id
        job = Job.objects.get(video_id=video_id)
        
        job.status = status
        if current_step:
            job.current_step = current_step
        if progress is not None:
            job.progress = progress
        
        job.save()
    except Job.DoesNotExist:
        # Se job não existe, ignora (pode ser um vídeo processado manualmente)
        pass
    except Exception as e:
        print(f"[job_utils] Erro ao atualizar job status: {e}")
