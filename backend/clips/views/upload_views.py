"""
Views para gerenciamento de uploads de vídeos com URLs pré-assinadas.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import uuid
from clips.services.storage_service import R2StorageService
from clips.models import Video, Organization, OrganizationMember
from clips.tasks import download_video_task


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_upload_url(request):
    """
    Gera uma URL pré-assinada para upload de vídeo no R2.
    
    Body (POST):
    {
        "filename": "video.mp4",
        "file_size": 1024000,
        "content_type": "video/mp4"
    }
    
    Response:
    {
        "upload_url": "https://...",
        "video_id": "uuid",
        "key": "videos/org_id/video_id/filename"
    }
    """
    try:
        user = request.user
        filename = request.data.get('filename')
        file_size = request.data.get('file_size')
        content_type = request.data.get('content_type', 'video/mp4')
        
        # Validações
        if not filename:
            return Response(
                {"error": "filename é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not file_size:
            return Response(
                {"error": "file_size é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        organization = getattr(user, "current_organization", None)
        if not organization:
            membership = (
                OrganizationMember.objects.filter(user_id=user.user_id, is_active=True)
                .select_related("organization")
                .first()
            )
            organization = membership.organization if membership else None
        if not organization:
            return Response(
                {"error": "Usuário não tem organização associada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obter video_id do request (gerado no frontend)
        video_id = request.data.get("video_id")
        if not video_id:
            return Response(
                {"error": "video_id é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        storage_path = f"videos/{organization.organization_id}/{video_id}/{filename}"
        
        video = Video.objects.create(
            video_id=video_id,
            organization_id=organization.organization_id,
            user_id=user.user_id,
            file=storage_path,
            storage_path=storage_path,
            status="ingestion",
        )
        
        storage_service = R2StorageService()
        key = storage_path
        
        upload_url = storage_service.generate_presigned_upload_url(
            key=key,
            content_type=content_type,
            expires_in=3600  # 1 hora
        )
        
        return Response(
            {
                "upload_url": upload_url,
                "video_id": str(video_id),
                "key": key,
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _extract_preview_metadata(source_url: str) -> dict:
    """Extrai metadados da URL sem baixar o vídeo (yt-dlp metadata-only)."""
    try:
        import yt_dlp
    except ImportError:
        return {}

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 20,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=False)

        if not isinstance(info, dict):
            return {}

        title = info.get("title")
        duration = info.get("duration")
        thumbnail = info.get("thumbnail")

        return {
            "title": title[:255] if isinstance(title, str) else None,
            "duration": float(duration) if duration is not None else None,
            "thumbnail_url": thumbnail if isinstance(thumbnail, str) else None,
        }
    except Exception:
        # Falha de metadados não deve bloquear a criação do vídeo.
        return {}


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_ingestion_from_url(request):
    """
    Inicia o download/processamento do vídeo (URL externa) após confirmação do usuário.

    Body:
    {
        "video_id": "uuid"
    }
    """
    try:
        user = request.user
        video_id = request.data.get('video_id')
        configuration = request.data.get("configuration") or {}
        if not video_id:
            return Response(
                {"error": "video_id é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        video = Video.objects.get(video_id=video_id, user_id=user.user_id)

        organization = getattr(user, "current_organization", None)
        if not organization:
            membership = (
                OrganizationMember.objects.filter(user_id=user.user_id, is_active=True)
                .select_related("organization")
                .first()
            )
            organization = membership.organization if membership else None
        if not organization:
            return Response(
                {"error": "Usuário não tem organização associada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Garante existência de Job para alimentar SSE e update_job_status no pipeline
        from clips.models import Job
        job, _ = Job.objects.get_or_create(
            video_id=video.video_id,
            defaults={
                "user_id": user.user_id,
                "organization_id": organization.organization_id,
                "status": "queued",
                "configuration": configuration,
                "credits_consumed": 0,
            },
        )

        if configuration and job.configuration != configuration:
            job.configuration = configuration
            job.save(update_fields=["configuration"])

        task = download_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.download.{organization.plan}",
        )

        video.task_id = task.id
        video.status = "queued"
        video.save(update_fields=["task_id", "status"])

        return Response(
            {
                "video_id": str(video.video_id),
                "job_id": str(job.job_id),
                "status": video.status,
                "task_id": task.id,
            },
            status=status.HTTP_200_OK,
        )

    except Video.DoesNotExist:
        return Response(
            {"error": "Vídeo não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_from_url(request):
    """
    Prepara um vídeo a partir de URL externa (YouTube, TikTok, Instagram, etc).

    Não dispara download automaticamente. O download deve ser iniciado depois,
    quando o usuário confirmar na tela de settings.

    Body (POST):
    {
        "source_url": "https://...",
        "source_type": "youtube" | "tiktok" | "instagram" | "url" | ...
    }

    Response:
    {
        "video_id": "uuid",
        "status": "queued",
        "title": "string",
        "duration": float|null,
        "file_size": int|null,
        "thumbnail_url": "url"|null,
        "task_id": null
    }
    """
    try:
        user = request.user
        source_url = request.data.get('source_url')
        source_type = request.data.get('source_type') or 'url'

        if not source_url:
            return Response(
                {"error": "source_url é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = getattr(user, "current_organization", None)
        if not organization:
            membership = (
                OrganizationMember.objects.filter(user_id=user.user_id, is_active=True)
                .select_related("organization")
                .first()
            )
            organization = membership.organization if membership else None
        if not organization:
            return Response(
                {"error": "Usuário não tem organização associada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prévia de metadados SEM download (para exibir na UI antes de iniciar tasks)
        preview = _extract_preview_metadata(source_url)
        title = preview.get("title") or f"Video from {source_type}"
        duration = preview.get("duration")
        thumbnail_url = preview.get("thumbnail_url")

        video_id = uuid.uuid4()
        video = Video.objects.create(
            video_id=video_id,
            organization_id=organization.organization_id,
            user_id=user.user_id,
            title=title,
            status="ingestion",
            source_type=source_type,
            source_url=source_url,
            duration=duration,
        )

        return Response(
            {
                "video_id": str(video.video_id),
                "status": video.status,
                "title": video.title,
                "duration": video.duration,
                "file_size": video.file_size,
                "thumbnail_url": thumbnail_url,
                "task_id": video.task_id,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_upload(request):
    """
    Confirma que o upload foi concluído e atualiza o status do vídeo.
    
    Body (POST):
    {
        "video_id": "uuid",
        "file_size": 1024000
    }
    
    Response:
    {
        "video_id": "uuid",
        "status": "queued"
    }
    """
    try:
        user = request.user
        video_id = request.data.get('video_id')
        file_size = request.data.get('file_size')
        
        if not video_id:
            return Response(
                {"error": "video_id é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Obter vídeo
        video = Video.objects.get(video_id=video_id, user_id=user.user_id)
        
        # Atualizar status e tamanho do arquivo
        video.status = "queued"
        video.file_size = file_size
        video.save()
        
        return Response(
            {
                "video_id": str(video.video_id),
                "status": video.status,
            },
            status=status.HTTP_200_OK,
        )
    
    except Video.DoesNotExist:
        return Response(
            {"error": "Vídeo não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
