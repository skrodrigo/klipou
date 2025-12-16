from typing import Any, Dict
from clips.models.team_member import TeamMember
from clips.models.organization import Organization


def me_service(user) -> Dict[str, Any]:
    # Busca a organização do usuário
    organization_id = None
    organization_data = None
    
    try:
        team_member = TeamMember.objects.filter(user_id=user.user_id).first()
        if team_member:
            organization_id = str(team_member.organization_id)
            organization = Organization.objects.get(organization_id=team_member.organization_id)
            organization_data = {
                "organization_id": str(organization.organization_id),
                "name": organization.name,
                "color": organization.color,
                "plan": organization.plan,
                "credits_available": organization.credits_available,
            }
    except Exception:
        pass
    
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "onboarding_completed": user.onboarding_completed,
        "onboarding_data": user.onboarding_data,
        "organization_id": organization_id,
        "organization": organization_data,
    }
