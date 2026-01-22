
from typing import Any, Dict, Optional, Tuple

from django.contrib.auth import get_user_model

User = get_user_model()


def register_service(
    email: str,
    password: str,
    organization_name: str = None,
) -> Tuple[Optional[User], Optional[str], Optional[Dict[str, Any]]]:
    if len(password) < 6:
        return None, "Password must be at least 6 characters", None

    if User.objects.filter(email=email).exists():
        return None, "Email already exists", None

    try:
        user = User.objects.create_user(email=email, password=password)
        return user, None, None
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
        return None, str(e), None

