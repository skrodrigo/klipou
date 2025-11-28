from typing import Optional, Tuple

from django.contrib.auth import get_user_model

User = get_user_model()


def register_service(email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
    if len(password) < 6:
        return None, "Password must be at least 6 characters"

    if User.objects.filter(email=email).exists():
        return None, "Email already exists"

    user = User.objects.create_user(email=email, password=password)
    return user, None
