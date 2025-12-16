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
from clips.models import Video, Organization


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
        
        # Obter organização do usuário
        from clips.models import TeamMember
        team_member = TeamMember.objects.filter(user_id=user.user_id).first()
        if not team_member:
            return Response(
                {"error": "Usuário não tem organização associada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        organization = Organization.objects.get(organization_id=team_member.organization_id)
        
        # Obter video_id do request (gerado no frontend)
        video_id = request.data.get("video_id")
        if not video_id:
            return Response(
                {"error": "video_id é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Definir caminho no R2 (estrutura correta: videos/org_id/video_id/file)
        storage_path = f"videos/{organization.organization_id}/{video_id}/{filename}"
        
        # Criar registro do vídeo no banco
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
