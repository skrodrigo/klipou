from typing import Optional, Tuple, Dict, Any
import uuid

from django.contrib.auth import get_user_model

User = get_user_model()


def register_service(
    email: str,
    password: str,
    organization_name: str = None
) -> Tuple[Optional[User], Optional[str], Optional[Dict[str, Any]]]:
    """
    Registra um novo usuário e cria uma organização.
    
    Args:
        email: Email do usuário
        password: Senha do usuário
        organization_name: Nome da organização (opcional)
    
    Returns:
        Tupla (user, error, organization_data)
    """
    if len(password) < 6:
        return None, "Password must be at least 6 characters", None

    if User.objects.filter(email=email).exists():
        return None, "Email already exists", None

    try:
        # Cria usuário
        user = User.objects.create_user(email=email, password=password)
        
        # Importa Organization aqui para evitar circular imports
        from clips.models import Organization, TeamMember
        
        # Cria organização padrão
        org_name = organization_name or f"{email.split('@')[0]}'s Organization"
        organization = Organization.objects.create(
            organization_id=uuid.uuid4(),
            name=org_name,
            plan="starter",
            credits_monthly=300,
            credits_available=300,
            credits_purchased=0,
            billing_email=email
        )
        
        # Adiciona usuário como líder da organização
        TeamMember.objects.create(
            organization_id=organization.organization_id,
            user_id=user.user_id,
            role="leader"
        )
        
        organization_data = {
            "organization_id": str(organization.organization_id),
            "name": organization.name,
            "plan": organization.plan,
            "credits_available": organization.credits_available,
        }
        
        return user, None, organization_data
    
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
        return None, str(e), None
