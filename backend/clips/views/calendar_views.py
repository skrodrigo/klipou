"""API para calendário e posts (schedules).

Este módulo expõe endpoints auxiliares para a tela de calendário:
- Listar clips disponíveis para agendamento por organização
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Clip
from ..services.storage_service import R2StorageService


@api_view(["GET"])
def list_available_clips(request, organization_id):
    """Lista clips disponíveis para agendamento dentro de uma organização.

    Query params:
    - user_organization_id: uuid (validação simples de permissão)
    - limit: padrão 50
    - offset: padrão 0
    """

    try:
        user_org_id = request.query_params.get("user_organization_id")
        if user_org_id != str(organization_id):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        qs = (
            Clip.objects.filter(video__organization_id=organization_id)
            .select_related("video")
            .order_by("-created_at")
        )

        total = qs.count()
        clips = qs[offset : offset + limit]

        storage = R2StorageService()

        def public_url(path):
            if not path:
                return None
            try:
                return storage.get_public_url(path)
            except Exception:
                return None

        return Response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "clips": [
                    {
                        "clip_id": str(c.clip_id),
                        "video_id": str(c.video.video_id) if c.video else None,
                        "title": c.title,
                        "created_at": c.created_at.isoformat(),
                        "video_url": public_url(c.storage_path),
                        "thumbnail_url": public_url(c.thumbnail_storage_path),
                        "ratio": c.ratio,
                        "duration": c.duration,
                    }
                    for c in clips
                ],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
