"""
View para atualizar perfil do usuário.
"""

import json
from django.contrib.auth import get_user_model
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()


@csrf_exempt
def update_profile_view(request: HttpRequest) -> JsonResponse:
    """
    Atualiza perfil do usuário autenticado.
    
    Body:
    {
        "email": "newemail@example.com",
        "onboarding_completed": true,
        "onboarding_data": {
            "content_type": "podcast",
            "platforms": ["tiktok", "instagram"],
            "objective": "reach",
            "language": "pt-BR",
            "frequency": "daily"
        }
    }
    """
    if request.method != "PUT":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    user = request.user

    # Atualiza email se fornecido
    if "email" in body:
        new_email = body.get("email")
        if User.objects.filter(email=new_email).exclude(user_id=user.user_id).exists():
            return JsonResponse({"detail": "Email already in use"}, status=400)
        user.email = new_email

    # Atualiza onboarding_completed se fornecido
    if "onboarding_completed" in body:
        user.onboarding_completed = body.get("onboarding_completed", False)

    # Atualiza onboarding_data se fornecido
    if "onboarding_data" in body:
        user.onboarding_data = body.get("onboarding_data", {})

    user.save()

    return JsonResponse(
        {
            "detail": "Profile updated successfully",
            "user": {
                "user_id": str(user.user_id),
                "email": user.email,
                "onboarding_completed": user.onboarding_completed,
                "onboarding_data": user.onboarding_data,
            },
        },
        status=200,
    )
