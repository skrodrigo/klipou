"""
Views para gerenciamento de onboarding de usuários.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from authentication.models import CustomUser
from ..services.onboarding_service import OnboardingService


@api_view(["POST"])
def complete_onboarding(request):
    """
    Completa o onboarding de um usuário.
    
    Body:
    {
        "user_id": 1,
        "content_type": "podcast|course|educational|marketing|personal",
        "platforms": ["tiktok", "instagram", "youtube"],
        "objective": "reach|leads|authority|reuse",
        "language": "pt-BR|en|es|fr|de|it|ja|zh|other",
        "frequency": "sporadic|weekly|daily"
    }
    """
    try:
        user_id = request.data.get("user_id")
        
        if not user_id:
            return Response(
                {"error": "user_id é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Extrai dados de onboarding
        onboarding_data = {
            "content_type": request.data.get("content_type"),
            "platforms": request.data.get("platforms"),
            "objective": request.data.get("objective"),
            "language": request.data.get("language"),
            "frequency": request.data.get("frequency"),
        }
        
        # Valida dados
        is_valid, error_message = OnboardingService.validate_onboarding_data(onboarding_data)
        if not is_valid:
            return Response(
                {"error": error_message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Salva onboarding
        success = OnboardingService.save_onboarding(user_id, onboarding_data)
        
        if not success:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(
            {
                "user_id": user_id,
                "onboarding_completed": True,
                "onboarding_data": onboarding_data,
            },
            status=status.HTTP_201_CREATED,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_onboarding(request, user_id):
    """
    Obtém dados de onboarding de um usuário.
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
def update_onboarding(request, user_id):
    """
    Atualiza dados de onboarding de um usuário.
    
    Body:
    {
        "content_type": "podcast",
        "platforms": ["tiktok", "instagram"],
        "objective": "reach",
        "language": "pt-BR",
        "frequency": "daily"
    }
    """
    try:
        # Extrai dados de onboarding
        onboarding_data = {}
        
        if "content_type" in request.data:
            onboarding_data["content_type"] = request.data.get("content_type")
        
        if "platforms" in request.data:
            onboarding_data["platforms"] = request.data.get("platforms")
        
        if "objective" in request.data:
            onboarding_data["objective"] = request.data.get("objective")
        
        if "language" in request.data:
            onboarding_data["language"] = request.data.get("language")
        
        if "frequency" in request.data:
            onboarding_data["frequency"] = request.data.get("frequency")
        
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
