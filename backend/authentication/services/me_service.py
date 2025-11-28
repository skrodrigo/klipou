from typing import Any, Dict


def me_service(user) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
    }
