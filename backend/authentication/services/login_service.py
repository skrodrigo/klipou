from typing import Optional

from django.contrib.auth import get_user_model

User = get_user_model()


def login_service(email: str, password: str) -> Optional[User]:
    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            return user
        return None
    except User.DoesNotExist:
        return None
