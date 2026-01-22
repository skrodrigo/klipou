
import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services import create_video_with_clips, list_videos


@csrf_exempt
def videos_list_create(request: HttpRequest) -> JsonResponse:
    """GET: Lista vídeos | POST: Cria vídeo e dispara task"""
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    if request.method == "GET":
        organization = getattr(request.user, "current_organization", None)
        if not organization:
            return JsonResponse({"results": []}, status=200)

        videos = list_videos(organization_id=str(organization.organization_id))
        return JsonResponse({"results": videos}, status=200)

    if request.method == "POST":
        title = _extract_title(request)
        file = request.FILES.get("file")

        if not title:
            return JsonResponse({"detail": "'title' is required"}, status=400)
        if not file:
            return JsonResponse({"detail": "'file' is required"}, status=400)

        organization = getattr(request.user, "current_organization", None)
        if not organization:
            return JsonResponse({"detail": "No active organization"}, status=400)

        video_data = create_video_with_clips(title, file)
        return JsonResponse(video_data, status=201)

    return JsonResponse({"detail": "Method not allowed"}, status=405)


def _extract_title(request: HttpRequest) -> str | None:
    """Extrai título de multipart/form-data ou JSON"""
    if request.content_type and request.content_type.startswith("multipart/"):
        upload = request.FILES.get("file")
        return upload.name if upload else None

    try:
        body = json.loads(request.body or b"{}")
        return body.get("title")
    except json.JSONDecodeError:
        return None

