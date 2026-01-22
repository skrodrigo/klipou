"""
Views para gerenciamento de onboarding de usuários.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.middleware.csrf import get_token
from authentication.models import CustomUser
from ..services.onboarding_service import OnboardingService
from ..models.organization import Organization
from ..models.organization_member import OrganizationMember
import uuid


@ensure_csrf_cookie
@api_view(["GET"])
def get_csrf_token(request):
    """
    Obtém o CSRF token para o frontend.
    """
    token = get_token(request)
    return Response({"csrfToken": token}, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(["POST", "GET"])
@permission_classes([IsAuthenticated])
def onboarding_view(request):
    """
    GET: Obtém dados de onboarding do usuário autenticado.
    POST: Completa o onboarding do usuário autenticado.
    
    Body (POST):
    {
        "organization_name": "Minha Empresa",
        "segment": "Tecnologia",
        "color": "#3b82f6",
        "platforms": ["TikTok", "Instagram Reels"],
        "objective": "Alcance / viralização",
        "content_type": "Podcast"
    }
    """
    try:
        user = request.user
        
        if request.method == "GET":
            onboarding = OnboardingService.get_onboarding(user.user_id)
            return Response(onboarding, status=status.HTTP_200_OK)
        
        if request.method == "POST":
            # Extrai dados de onboarding
            onboarding_data = {
                "organization_name": request.data.get("organization_name"),
                "segment": request.data.get("segment"),
                "color": request.data.get("color"),
                "platforms": request.data.get("platforms", []),
                "objective": request.data.get("objective"),
                "content_type": request.data.get("content_type"),
            }
            
            # Valida dados obrigatórios
            if not onboarding_data.get("organization_name"):
                return Response(
                    {"error": "organization_name é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not onboarding_data.get("segment"):
                return Response(
                    {"error": "segment é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not onboarding_data.get("color"):
                return Response(
                    {"error": "color é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not onboarding_data.get("platforms"):
                return Response(
                    {"error": "platforms é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not onboarding_data.get("objective"):
                return Response(
                    {"error": "objective é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if not onboarding_data.get("content_type"):
                return Response(
                    {"error": "content_type é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Cria organização se não existir
            try:
                organization = Organization.objects.create(
                    organization_id=uuid.uuid4(),
                    name=onboarding_data.get("organization_name"),
                    color=onboarding_data.get("color", "#3b82f6"),
                    plan="starter",
                    credits_monthly=300,
                    credits_available=300,
                    credits_purchased=0,
                    billing_email=user.email,
                )
                
                # Adiciona usuário como admin da organização
                OrganizationMember.objects.create(
                    organization=organization,
                    user=user,
                    role="admin",
                    is_active=True,
                )

                if hasattr(user, "current_organization"):
                    user.current_organization = organization
                    user.save(update_fields=["current_organization"])
            except Exception as e:
                return Response(
                    {"error": f"Erro ao criar organização: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Salva onboarding
            success = OnboardingService.save_onboarding(user.user_id, onboarding_data)
            
            if not success:
                return Response(
                    {"error": "Erro ao salvar onboarding"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            return Response(
                {
                    "detail": "Onboarding concluído com sucesso",
                    "onboarding_completed": True,
                    "onboarding_data": onboarding_data,
                    "organization": {
                        "organization_id": str(organization.organization_id),
                        "name": organization.name,
                        "color": organization.color,
                        "plan": organization.plan,
                        "credits_available": organization.credits_available,
                    },
                },
                status=status.HTTP_201_CREATED,
            )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_onboarding(request, user_id):
    """
    Obtém dados de onboarding de um usuário (endpoint legado).
    """
    try:
        onboarding = OnboardingService.get_onboarding(user_id)
        
        if not onboarding:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(onboarding, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_onboarding(request, user_id):
    """
    Atualiza dados de onboarding de um usuário (endpoint legado).
    """
    try:
        # Extrai dados de onboarding
        onboarding_data = {}
        
        if "organization_name" in request.data:
            onboarding_data["organization_name"] = request.data.get("organization_name")
        
        if "industry" in request.data:
            onboarding_data["industry"] = request.data.get("industry")
        
        if "team_size" in request.data:
            onboarding_data["team_size"] = request.data.get("team_size")
        
        if "content_type" in request.data:
            onboarding_data["content_type"] = request.data.get("content_type")
        
        if "integrations" in request.data:
            onboarding_data["integrations"] = request.data.get("integrations")
        
        if "goals" in request.data:
            onboarding_data["goals"] = request.data.get("goals")
        
        if not onboarding_data:
            return Response(
                {"error": "Nenhum dado para atualizar"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Atualiza onboarding
        success = OnboardingService.update_onboarding(user_id, onboarding_data)
        
        if not success:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Retorna dados atualizados
        updated_onboarding = OnboardingService.get_onboarding(user_id)
        
        return Response(updated_onboarding, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
