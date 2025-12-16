"""
Serviço de onboarding para usuários.
"""

from typing import Dict, Any
from authentication.models import CustomUser


class OnboardingService:
    """Serviço para gerenciar dados de onboarding."""

    @staticmethod
    def save_onboarding(user_id, onboarding_data: Dict[str, Any]) -> bool:
        """
        Salva dados de onboarding para um usuário.
        
        Args:
            user_id: ID do usuário (UUID)
            onboarding_data: Dados de onboarding (content_type, platforms, objective, language, frequency)
        
        Returns:
            True se salvo com sucesso
        """
        try:
            user = CustomUser.objects.get(user_id=user_id)
            user.onboarding_data = onboarding_data
            user.onboarding_completed = True
            user.save()
            return True
        except CustomUser.DoesNotExist:
            return False
        except Exception as e:
            print(f"Erro ao salvar onboarding: {e}")
            return False

    @staticmethod
    def get_onboarding(user_id) -> Dict[str, Any]:
        """
        Obtém dados de onboarding de um usuário.
        
        Args:
            user_id: ID do usuário (UUID)
        
        Returns:
            Dicionário com dados de onboarding
        """
        try:
            user = CustomUser.objects.get(user_id=user_id)
            return {
                "onboarding_completed": user.onboarding_completed,
                "onboarding_data": user.onboarding_data,
            }
        except CustomUser.DoesNotExist:
            return {}

    @staticmethod
    def update_onboarding(user_id, onboarding_data: Dict[str, Any]) -> bool:
        """
        Atualiza dados de onboarding de um usuário.
        
        Args:
            user_id: ID do usuário (UUID)
            onboarding_data: Novos dados de onboarding
        
        Returns:
            True se atualizado com sucesso
        """
        try:
            user = CustomUser.objects.get(user_id=user_id)
            # Mescla dados existentes com novos dados
            if user.onboarding_data:
                user.onboarding_data.update(onboarding_data)
            else:
                user.onboarding_data = onboarding_data
            user.save()
            return True
        except CustomUser.DoesNotExist:
            return False
        except Exception as e:
            print(f"Erro ao atualizar onboarding: {e}")
            return False

    @staticmethod
    def validate_onboarding_data(data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Valida dados de onboarding.
        
        Args:
            data: Dados de onboarding
        
        Returns:
            Tupla (válido, mensagem de erro)
        """
        required_fields = ["content_type", "platforms", "objective", "language", "frequency"]
        
        for field in required_fields:
            if field not in data:
                return False, f"Campo obrigatório faltando: {field}"
        
        # Valida content_type
        valid_content_types = ["podcast", "course", "educational", "marketing", "personal"]
        if data["content_type"] not in valid_content_types:
            return False, f"content_type inválido: {data['content_type']}"
        
        # Valida platforms (deve ser lista)
        if not isinstance(data["platforms"], list) or len(data["platforms"]) == 0:
            return False, "platforms deve ser uma lista não vazia"
        
        valid_platforms = ["tiktok", "instagram", "youtube", "linkedin", "twitter"]
        for platform in data["platforms"]:
            if platform not in valid_platforms:
                return False, f"Plataforma inválida: {platform}"
        
        # Valida objective
        valid_objectives = ["reach", "leads", "authority", "reuse"]
        if data["objective"] not in valid_objectives:
            return False, f"objective inválido: {data['objective']}"
        
        # Valida language
        valid_languages = ["pt-BR", "en", "es", "fr", "de", "it", "ja", "zh", "other"]
        if data["language"] not in valid_languages:
            return False, f"language inválido: {data['language']}"
        
        # Valida frequency
        valid_frequencies = ["sporadic", "weekly", "daily"]
        if data["frequency"] not in valid_frequencies:
            return False, f"frequency inválido: {data['frequency']}"
        
        return True, ""
