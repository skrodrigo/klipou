from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.logout_service import logout_service


@csrf_exempt
def logout_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    logout_service(request)
    return JsonResponse({"detail": "Logged out"}, status=200)
