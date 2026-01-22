from typing import Any, Dict
from clips.models.organization_member import OrganizationMember


def me_service(user) -> Dict[str, Any]:
    # Busca a organização do usuário
    organization_id = None
    organization_data = None
    
    try:
        organization = getattr(user, "current_organization", None)
        if not organization:
            membership = (
                OrganizationMember.objects.filter(user_id=user.user_id, is_active=True)
                .select_related("organization")
                .first()
            )
            organization = membership.organization if membership else None

        if organization:
            organization_id = str(organization.organization_id)
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
