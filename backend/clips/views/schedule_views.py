"""
Views para gerenciamento de agendamento de posts em redes sociais.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime

from ..models import Schedule, Clip, Integration


@api_view(["GET"])
def list_schedules(request, organization_id):
    """
    Lista todos os agendamentos de uma organização.
    
    Query params:
    - status: filtering por status (scheduled, posted, failed, canceled)
    - platform: filtering por plataforma
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        status_filter = request.query_params.get("status")
        platform_filter = request.query_params.get("platform")
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        # Valida permissão
        user_org_id = request.query_params.get("user_organization_id")
        if user_org_id != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = Schedule.objects.filter(
            clip__video__organization_id=organization_id
        ).order_by("-scheduled_time")

        if status_filter:
            query = query.filter(status=status_filter)

        if platform_filter:
            query = query.filter(platform=platform_filter)

        total = query.count()
        schedules = query[offset : offset + limit]

        return Response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "schedules": [
                    {
                        "schedule_id": str(schedule.schedule_id),
                        "clip_id": str(schedule.clip.clip_id),
                        "clip_title": schedule.clip.title,
                        "platform": schedule.platform,
                        "status": schedule.status,
                        "scheduled_time": schedule.scheduled_time.isoformat() if schedule.scheduled_time else None,
                        "posted_at": schedule.posted_at.isoformat() if schedule.posted_at else None,
                        "post_url": schedule.post_url,
                        "created_at": schedule.created_at.isoformat(),
                    }
                    for schedule in schedules
                ],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def create_schedule(request):
    """
    Cria um novo agendamento de post.
    
    Body:
    {
        "clip_id": "uuid",
        "platform": "tiktok|instagram|youtube|facebook|linkedin|twitter",
        "scheduled_time": "2025-12-20T15:30:00Z",
        "organization_id": "uuid",
        "user_id": "uuid"
    }
    """
    try:
        clip_id = request.data.get("clip_id")
        platform = request.data.get("platform")
        scheduled_time = request.data.get("scheduled_time")
        organization_id = request.data.get("organization_id")
        user_id = request.data.get("user_id")

        # Valida clip
        clip = Clip.objects.get(clip_id=clip_id)

        # Valida permissão
        if str(clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valida plataforma
        valid_platforms = ["tiktok", "instagram", "youtube", "facebook", "linkedin", "twitter"]
        if platform not in valid_platforms:
            return Response(
                {"error": f"Invalid platform. Valid: {', '.join(valid_platforms)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida integração
        integration = Integration.objects.filter(
            organization_id=organization_id,
            platform=platform,
            is_active=True,
        ).first()

        if not integration:
            return Response(
                {"error": f"Integration with {platform} not connected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Converte scheduled_time
        if scheduled_time:
            scheduled_time = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
        else:
            scheduled_time = None

        # Cria agendamento
        schedule = Schedule.objects.create(
            clip=clip,
            user_id=user_id,
            platform=platform,
            scheduled_time=scheduled_time,
            status="scheduled",
        )

        return Response(
            {
                "schedule_id": str(schedule.schedule_id),
                "clip_id": str(clip_id),
                "platform": platform,
                "status": "scheduled",
                "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
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


@api_view(["PUT"])
def update_schedule(request, schedule_id):
    """
    Atualiza um agendamento.
    
    Body:
    {
        "scheduled_time": "2025-12-20T15:30:00Z",
        "organization_id": "uuid"
    }
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        organization_id = request.data.get("organization_id")

        # Valida permissão
        if str(schedule.clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valida status (só pode editar se agendado)
        if schedule.status != "scheduled":
            return Response(
                {"error": f"Cannot edit schedule with status '{schedule.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Atualiza scheduled_time
        scheduled_time = request.data.get("scheduled_time")
        if scheduled_time:
            schedule.scheduled_time = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
            schedule.save()

        return Response(
            {
                "schedule_id": str(schedule.schedule_id),
                "scheduled_time": schedule.scheduled_time.isoformat() if schedule.scheduled_time else None,
            },
            status=status.HTTP_200_OK,
        )

    except Schedule.DoesNotExist:
        return Response(
            {"error": "Schedule not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def cancel_schedule(request, schedule_id):
    """
    Cancela um agendamento.
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        organization_id = request.data.get("organization_id")

        # Valida permissão
        if str(schedule.clip.video.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valida status
        if schedule.status not in ["scheduled", "failed"]:
            return Response(
                {"error": f"Cannot cancel schedule with status '{schedule.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Marca como cancelado
        schedule.status = "canceled"
        schedule.save()

        return Response(
            {
                "schedule_id": str(schedule.schedule_id),
                "status": "canceled",
            },
            status=status.HTTP_200_OK,
        )

    except Schedule.DoesNotExist:
        return Response(
            {"error": "Schedule not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
