import json
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt

from ..services.clips_service import create_video_clip, list_video_clips


@csrf_exempt
def clips_list_create(request: HttpRequest):
    if request.method == "GET":
        clips = list_video_clips()
        return JsonResponse({"results": clips}, status=200)

    if request.method == "POST":
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON body"}, status=400)

        title = body.get("title")
        if not title:
            return JsonResponse({"detail": "'title' is required"}, status=400)

        clip = create_video_clip(title=title)
        return JsonResponse(clip, status=201)

    return JsonResponse({"detail": "Method not allowed"}, status=405)
