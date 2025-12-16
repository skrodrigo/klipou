from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import uuid

from ..services.list_video_clips_service import list_video_clips


@csrf_exempt
def video_clips_list(request: HttpRequest, video_id) -> JsonResponse:
    """
    GET: Lista todos os clips de um vídeo específico
    
    Args:
        video_id: UUID do vídeo (pode ser string ou objeto UUID)
    """
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        # Converte para string se for UUID object
        video_id_str = str(video_id)
        clips = list_video_clips(video_id_str)
        return JsonResponse({"results": clips}, status=200)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)
