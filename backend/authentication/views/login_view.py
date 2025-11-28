import json

from django.contrib.auth import login
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.login_service import login_service


@csrf_exempt
def login_view(request: HttpRequest) -> JsonResponse:
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

    user = login_service(email=email, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials"}, status=400)

    login(request, user)
    return JsonResponse({"detail": "Logged in", "email": user.email}, status=200)
