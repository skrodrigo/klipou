from typing import Any, Dict
import uuid

from ..models import Video, Job, Organization, CreditTransaction
import requests

from ..tasks import download_video_task
from .storage_service import R2StorageService


def create_video_with_clips(
    title: str,
    file,
    organization_id: str = None,
    user_id: str = None,
    configuration: dict = None,
) -> Dict[str, Any]:
    """
    Cria um vídeo e dispara job de processamento automaticamente.
    
    Fluxo:
    1. Valida créditos
    2. Faz upload para R2
    3. Deduz créditos
    4. Cria Job automaticamente
    5. Dispara primeira task
    
    Args:
        title: Título do vídeo
        file: Arquivo de vídeo
        organization_id: ID da organização
        user_id: ID do usuário
        configuration: Configurações do job (language, target_ratios, etc)
        
    Returns:
        Dict com dados do vídeo, job e task_id
        
    Raises:
        Exception: Se validação, upload ou criação de job falhar
    """
    # Gera IDs únicos
    video_id = uuid.uuid4()
    org_id = organization_id or str(uuid.uuid4())
    
    # Obtém organização
    try:
        org = Organization.objects.get(organization_id=org_id)
    except Organization.DoesNotExist:
        raise Exception(f"Organization {org_id} not found")
    
    # Calcula créditos necessários (1 crédito = 1 minuto)
    # Usa tamanho do arquivo como aproximação se duração não estiver disponível
    file_size_mb = file.size / (1024 * 1024)
    estimated_duration_minutes = max(1, int(file_size_mb / 10))  # Aproximação: 10MB por minuto
    credits_needed = estimated_duration_minutes
    
    # Valida créditos
    if org.credits_available < credits_needed:
        raise Exception(
            f"Insufficient credits. Need {credits_needed}, have {org.credits_available}"
        )
    
    # Cria vídeo no banco
    video = Video.objects.create(
        video_id=video_id,
        organization_id=org_id,
        user_id=user_id,
        title=title,
        file=file,
        original_filename=file.name,
        file_size=file.size,
        status="ingestion",
        source_type="upload",
    )

    try:
        # Faz upload do vídeo original para R2
        storage = R2StorageService()
        storage_path = storage.upload_video(
            file_path=video.file.path,
            organization_id=org_id,
            video_id=str(video_id),
            original_filename=file.name,
        )
        video.storage_path = storage_path
        video.save()
    except Exception as e:
        video.status = "failed"
        video.error_code = "UPLOAD_ERROR"
        video.error_message = f"Falha ao fazer upload para R2: {str(e)}"
        video.save()
        raise Exception(f"Erro ao fazer upload do vídeo para R2: {e}") from e

    # Deduz créditos
    org.credits_available -= credits_needed
    org.save()

    # Registra transação de crédito
    CreditTransaction.objects.create(
        organization=org,
        amount=credits_needed,
        type="consumption",
        reason=f"Processamento de vídeo - {title}",
        balance_after=org.credits_available,
    )

    # Cria Job automaticamente
    job = Job.objects.create(
        user_id=user_id,
        organization_id=org_id,
        video_id=video_id,
        status="queued",
        configuration=configuration or {},
        credits_consumed=credits_needed,
    )

    # Dispara primeira task do pipeline: download_video_task
    task = download_video_task.apply_async(
        args=[video.id],
        queue=f"video.download.{org.plan}",
    )

    job.task_id = task.id
    job.save()

    video.task_id = task.id
    video.save()
    
    return {
        "id": video.id,
        "video_id": str(video.video_id),
        "job_id": str(job.job_id),
        "title": video.title,
        "status": "queued",
        "task_id": task.id,
        "storage_path": video.storage_path,
        "credits_consumed": credits_needed,
        "credits_remaining": org.credits_available,
        "created_at": video.created_at.isoformat(),
    }
