"""
Views para gerenciamento de clips.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import FileResponse
import os

from ..models import Clip, Video, CreditTransaction
from ..services.storage_service import R2StorageService


@api_view(["GET"])
def download_clip(request, clip_id):
    """
    Faz download de um clip.
    
    Response: Arquivo MP4 do clip
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)

        # Valida permissão (usuário deve ser da mesma organização)
        organization_id = request.query_params.get("organization_id")
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Obtém URL assinada do R2
        storage = R2StorageService()
        signed_url = storage.get_signed_url(clip.storage_path, expiration=3600)

        return Response(
            {
                "clip_id": str(clip.clip_id),
                "title": clip.title,
                "download_url": signed_url,
                "expires_in": 3600,
            },
            status=status.HTTP_200_OK,
        )

    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def delete_clip(request, clip_id):
    """
    Deleta um clip (soft delete).
    
    Valida permissão e marca como deletado.
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)

        # Valida permissão
        organization_id = request.data.get("organization_id")
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            storage = R2StorageService()
            if clip.storage_path:
                storage.delete_file(clip.storage_path)
            if clip.thumbnail_storage_path:
                storage.delete_file(clip.thumbnail_storage_path)
        except Exception as e:
            print(f"Aviso: Falha ao deletar arquivo do R2: {e}")

        clip.delete()

        return Response(
            {
                "clip_id": str(clip.clip_id),
                "status": "deleted",
            },
            status=status.HTTP_200_OK,
        )

    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def submit_clip_feedback(request, clip_id):
    """
    Submete feedback sobre um clip (bom/ruim).
    
    Body:
    {
        "rating": "good" | "bad",
        "organization_id": "uuid"
    }
    
    O feedback é usado para melhorar o ranking futuro de clips.
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)
        rating = request.data.get("rating")  # "good" ou "bad"
        organization_id = request.data.get("organization_id")

        # Valida permissão
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valida rating
        if rating not in ["good", "bad"]:
            return Response(
                {"error": "Rating must be 'good' or 'bad'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cria ou atualiza feedback
        from ..models import ClipFeedback
        from django.utils import timezone

        feedback, created = ClipFeedback.objects.update_or_create(
            clip=clip,
            user_id=request.data.get("user_id"),
            defaults={"rating": rating},
        )

        return Response(
            {
                "clip_id": str(clip.clip_id),
                "rating": rating,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_clip_details(request, clip_id):
    """
    Obtém detalhes de um clip.
    
    Response:
    {
        "clip_id": "uuid",
        "title": "string",
        "duration": float,
        "engagement_score": int,
        "ratio": "9:16|1:1|16:9",
        "created_at": "datetime",
        "preview_url": "signed_url"
    }
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)

        # Valida permissão
        organization_id = request.query_params.get("organization_id")
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Gera URL assinada para preview
        storage = R2StorageService()
        preview_url = storage.get_signed_url(clip.storage_path, expiration=3600)

        return Response(
            {
                "clip_id": str(clip.clip_id),
                "title": clip.title,
                "video_id": str(clip.video.video_id),
                "start_time": float(clip.start_time),
                "end_time": float(clip.end_time),
                "duration": clip.duration,
                "engagement_score": clip.engagement_score,
                "ratio": clip.ratio,
                "created_at": clip.created_at.isoformat(),
                "preview_url": preview_url,
                "storage_path": clip.storage_path,
            },
            status=status.HTTP_200_OK,
        )

    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def rename_clip(request, clip_id):
    """
    Renomeia um clip.
    
    Body:
    {
        "title": "novo título",
        "organization_id": "uuid"
    }
    """
    try:
        clip = Clip.objects.get(clip_id=clip_id)
        
        # Valida permissão
        organization_id = request.data.get("organization_id")
        if str(clip.video.organization_id) != organization_id:
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
        clip.title = title
        clip.save()
        
        return Response(
            {
                "clip_id": str(clip.clip_id),
                "title": clip.title,
                "updated_at": clip.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
    
    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def duplicate_clip(request, clip_id):
    """
    Duplica um clip.
    
    Body:
    {
        "organization_id": "uuid"
    }
    
    Response:
    {
        "clip_id": "novo uuid",
        "title": "título (cópia)",
        "storage_path": "mesmo caminho do original"
    }
    """
    try:
        import uuid
        
        clip = Clip.objects.get(clip_id=clip_id)
        
        # Valida permissão
        organization_id = request.data.get("organization_id")
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Cria novo clip com os mesmos dados
        new_clip = Clip.objects.create(
            clip_id=uuid.uuid4(),
            video=clip.video,
            title=f"{clip.title} (cópia)",
            start_time=clip.start_time,
            end_time=clip.end_time,
            duration=clip.duration,
            ratio=clip.ratio,
            storage_path=clip.storage_path,
            file_size=clip.file_size,
            engagement_score=clip.engagement_score,
            confidence_score=clip.confidence_score,
            transcript=clip.transcript,
            thumbnail_storage_path=clip.thumbnail_storage_path,
        )
        
        return Response(
            {
                "clip_id": str(new_clip.clip_id),
                "title": new_clip.title,
                "storage_path": new_clip.storage_path,
            },
            status=status.HTTP_201_CREATED,
        )
    
    except Clip.DoesNotExist:
        return Response(
            {"error": "Clip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
