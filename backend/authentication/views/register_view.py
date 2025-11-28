import json

from django.contrib.auth import login
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.register_service import register_service


@csrf_exempt
def register_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        return JsonResponse({"detail": "'email' and 'password' are required"}, status=400)

    user, error = register_service(email=email, password=password)
    if error is not None or user is None:
        return JsonResponse({"detail": error or "Invalid data"}, status=400)

    login(request, user)
    return JsonResponse(
        {"detail": "User registered successfully", "email": user.email},
        status=201,
    )
