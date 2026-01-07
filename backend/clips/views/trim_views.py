from __future__ import annotations

from typing import Any, Dict, List

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import Clip, Transcript, Video
from ..services.storage_service import R2StorageService


def _normalize_segments(segments: Any) -> List[Dict[str, Any]]:
    if not isinstance(segments, list):
        return []

    out: List[Dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        if start < 0 or end < 0 or end <= start:
            continue
        out.append(
            {
                "start": float(start),
                "end": float(end),
                "text": (str(text) if text is not None else "").strip(),
            }
        )

    return out

@api_view(["GET"])
def get_video_trim_context(request, video_id):
    """Retorna dados necessários para o dialog de trim."""
    try:
        video = Video.objects.get(video_id=video_id)

        organization_id = request.query_params.get("organization_id") or request.headers.get("X-Organization-ID")
        if not organization_id or str(video.organization_id) != str(organization_id):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        storage = R2StorageService()

        video_url = None
        if video.storage_path:
            try:
                video_url = storage.get_public_url(video.storage_path)
            except Exception:
                video_url = None

        transcript = Transcript.objects.filter(video=video).first()
        segments = _normalize_segments(transcript.segments if transcript else [])

        return Response(
            {
                "video_id": str(video.video_id),
                "video_url": video_url,
                "transcript": {
                    "language": transcript.language if transcript else None,
                    "segments": segments,
                },
            },
            status=status.HTTP_200_OK,
        )

    except Video.DoesNotExist:
        return Response({"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["PUT"])
def update_clip_trim(request, clip_id):
    """Atualiza o corte (start/end) de um clip."""
    try:
        clip = Clip.objects.get(clip_id=clip_id)

        organization_id = request.data.get("organization_id") or request.query_params.get("organization_id")
        if not organization_id or str(clip.video.organization_id) != str(organization_id):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")

        if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
            return Response({"error": "start_time and end_time must be numbers"}, status=status.HTTP_400_BAD_REQUEST)

        start_time_f = float(start_time)
        end_time_f = float(end_time)

        if start_time_f < 0 or end_time_f <= start_time_f:
            return Response({"error": "Invalid time range"}, status=status.HTTP_400_BAD_REQUEST)

        if (
            isinstance(clip.video.duration, (int, float))
            and clip.video.duration
            and end_time_f > float(clip.video.duration)
        ):
            return Response({"error": "end_time exceeds video duration"}, status=status.HTTP_400_BAD_REQUEST)

        clip.start_time = start_time_f
        clip.end_time = end_time_f
        clip.duration = max(0.0, end_time_f - start_time_f)
        clip.save(update_fields=["start_time", "end_time", "duration", "updated_at"])

        return Response(
            {
                "clip_id": str(clip.clip_id),
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "duration": clip.duration,
                "updated_at": clip.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Clip.DoesNotExist:
        return Response({"error": "Clip not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
