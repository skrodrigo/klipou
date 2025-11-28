from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.me_service import me_service


@csrf_exempt
def me_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    data = me_service(request.user)
    return JsonResponse(data, status=200)
