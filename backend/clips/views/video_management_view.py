"""
Views para gerenciamento de vídeos (projetos).
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Video
from ..services.storage_service import R2StorageService


@api_view(["GET"])
def get_video_details(request, video_id):
    """
    Obtém detalhes de um vídeo.
    
    Response:
    {
        "video_id": "uuid",
        "title": "string",
        "status": "string",
        "duration": float,
        "resolution": "string",
        "file_size": int,
        "clips_count": int,
        "created_at": "datetime",
        "thumbnail_url": "url"
    }
    """
    try:
        video = Video.objects.get(video_id=video_id)
        
        # Valida permissão (aceita como query param ou header)
        organization_id = request.query_params.get("organization_id") or request.headers.get("X-Organization-ID")
        if not organization_id or str(video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Gera URL da thumbnail
        thumbnail_url = None
        if video.thumbnail_storage_path:
            try:
                storage = R2StorageService()
                thumbnail_url = storage.get_public_url(video.thumbnail_storage_path)
            except Exception:
                pass
        
        return Response(
            {
                "video_id": str(video.video_id),
                "title": video.title,
                "status": video.status,
                "duration": video.duration,
                "resolution": video.resolution,
                "file_size": video.file_size,
                "clips_count": video.clips.count(),
                "created_at": video.created_at.isoformat(),
                "thumbnail_url": thumbnail_url,
            },
            status=status.HTTP_200_OK,
        )
    
    except Video.DoesNotExist:
        return Response(
            {"error": "Video not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def rename_video(request, video_id):
    """
    Renomeia um vídeo (projeto).
    
    Body:
    {
        "title": "novo título",
        "organization_id": "uuid"
    }
    """
    try:
        video = Video.objects.get(video_id=video_id)
        
        # Valida permissão
        organization_id = request.data.get("organization_id")
        if str(video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Valida título
        title = request.data.get("title", "").strip()
        if not title:
            return Response(
                {"error": "Title is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Atualiza título
        video.title = title
        video.save()
        
        return Response(
            {
                "video_id": str(video.video_id),
                "title": video.title,
                "updated_at": video.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
    
    except Video.DoesNotExist:
        return Response(
            {"error": "Video not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def delete_video(request, video_id):
    """
    Deleta um vídeo (projeto) - soft delete.
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        video = Video.objects.get(video_id=video_id)
        
        # Valida permissão
        organization_id = request.data.get("organization_id")
        if str(video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Soft delete - marca como deletado
        video.delete()
        
        return Response(
            {
                "video_id": str(video.video_id),
                "status": "deleted",
            },
            status=status.HTTP_200_OK,
        )
    
    except Video.DoesNotExist:
        return Response(
            {"error": "Video not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
