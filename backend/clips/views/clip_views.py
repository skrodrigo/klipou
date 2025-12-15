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

        # Soft delete
        clip.is_deleted = True
        clip.save()

        # Opcionalmente, deleta arquivo do R2
        try:
            storage = R2StorageService()
            storage.delete_file(clip.storage_path)
        except Exception as e:
            print(f"Aviso: Falha ao deletar arquivo do R2: {e}")

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
