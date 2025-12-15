"""
Views para gerenciamento de membros da equipe em organizações.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from uuid import uuid4

from ..models import TeamMember, Organization
from ..services.email_service import EmailService


@api_view(["GET"])
def list_team_members(request, organization_id):
    """
    Lista todos os membros de uma organização.
    
    Query params:
    - role: filtering por papel (member, co-leader, leader)
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        role_filter = request.query_params.get("role")
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        query = TeamMember.objects.filter(
            organization_id=organization_id,
            is_active=True
        ).order_by("-joined_at")

        if role_filter:
            query = query.filter(role=role_filter)

        total = query.count()
        members = query[offset : offset + limit]

        return Response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "members": [
                    {
                        "member_id": str(member.member_id),
                        "user_id": str(member.user_id),
                        "role": member.role,
                        "joined_at": member.joined_at.isoformat(),
                    }
                    for member in members
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
def invite_team_member(request, organization_id):
    """
    Convida um novo membro para a organização.
    
    Body:
    {
        "email": "member@example.com",
        "role": "member|co-leader|leader",
        "organization_id": "uuid"
    }
    """
    try:
        email = request.data.get("email")
        role = request.data.get("role", "member")
        
        if not email:
            return Response(
                {"error": "email é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida papel
        valid_roles = ["member", "co-leader", "leader"]
        if role not in valid_roles:
            return Response(
                {"error": f"Papel inválido. Válidos: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida organização
        org = Organization.objects.get(organization_id=organization_id)
        
        # TODO: Implementar lógica de convite com token
        # Por enquanto, apenas registra a intenção
        
        # Envia email de convite
        invite_link = f"https://app.klipai.com/invite/{uuid4()}"
        EmailService.send_team_invitation(email, org.name, invite_link)
        
        return Response(
            {
                "status": "invitation_sent",
                "email": email,
                "role": role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organização não encontrada"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def remove_team_member(request, organization_id, member_id):
    """
    Remove um membro da organização.
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        member = TeamMember.objects.get(
            member_id=member_id,
            organization_id=organization_id
        )
        
        # Soft delete
        member.is_active = False
        member.save()
        
        return Response(
            {
                "member_id": str(member.member_id),
                "status": "removed",
            },
            status=status.HTTP_200_OK,
        )

    except TeamMember.DoesNotExist:
        return Response(
            {"error": "Membro não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def update_team_member_role(request, organization_id, member_id):
    """
    Atualiza o papel de um membro.
    
    Body:
    {
        "role": "member|co-leader|leader",
        "organization_id": "uuid"
    }
    """
    try:
        role = request.data.get("role")
        
        if not role:
            return Response(
                {"error": "role é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Valida papel
        valid_roles = ["member", "co-leader", "leader"]
        if role not in valid_roles:
            return Response(
                {"error": f"Papel inválido. Válidos: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        member = TeamMember.objects.get(
            member_id=member_id,
            organization_id=organization_id
        )
        
        member.role = role
        member.save()
        
        return Response(
            {
                "member_id": str(member.member_id),
                "role": member.role,
            },
            status=status.HTTP_200_OK,
        )

    except TeamMember.DoesNotExist:
        return Response(
            {"error": "Membro não encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
