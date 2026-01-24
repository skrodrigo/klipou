import logging
import os
import numpy as np
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def reframe_video_task(self, video_id: str) -> dict:
    try:
        logger.info(f"Iniciando Smart Reframing para video_id: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "reframing"
        video.current_step = "reframing"
        video.save()
        update_job_status(str(video.video_id), "reframing", progress=80, current_step="reframing")

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        input_path = os.path.join(video_dir, "video_normalized.mp4")

        if not os.path.exists(input_path):
            raise Exception("Vídeo normalizado não encontrado")

        reframe_data = _detect_smart_crop(input_path)

        transcript.reframe_data = reframe_data
        transcript.save()

        video.last_successful_step = "reframing"
        video.status = "clipping"
        video.current_step = "clipping"
        video.save()

        update_job_status(str(video.video_id), "clipping", progress=82, current_step="clipping")
        
        from .caption_clips_task import caption_clips_task
        caption_clips_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.clip.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "face_detected": reframe_data.get("face_detected"),
            "crop_center_x": reframe_data.get("crops", {}).get("9:16", {}).get("center_x")
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro no reframing {video_id}: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

            update_job_status(str(video.video_id), "failed", progress=100, current_step="reframing")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _detect_smart_crop(video_path: str) -> dict:
    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        raise Exception("Instale: pip install opencv-python mediapipe")

    FaceDetector = mp.tasks.vision.FaceDetector
    FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
    VisionRunningMode = mp.tasks.vision.RunningMode
    BaseOptions = mp.tasks.BaseOptions

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception("Erro ao abrir vídeo para análise")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    model_path = getattr(settings, "MEDIAPIPE_FACE_MODEL_PATH", None) or os.path.join(
        settings.BASE_DIR, "assets", "blaze_face_short_range.tflite"
    )
    if not os.path.exists(model_path):
        cap.release()
        stable_center_x = width // 2
        crops = _calculate_crops(width, height, stable_center_x)
        return {
            "face_detected": False,
            "video_resolution": f"{width}x{height}",
            "crops": crops,
            "raw_face_centers_count": 0,
        }

    options = FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        min_detection_confidence=0.6,
        running_mode=VisionRunningMode.IMAGE
    )

    face_centers_x = []

    sample_every_seconds = float(getattr(settings, "REFRAME_SAMPLE_EVERY_SECONDS", 1.0) or 1.0)
    max_samples = int(getattr(settings, "REFRAME_MAX_FACE_SAMPLES", 240) or 240)
    min_samples_to_stop = int(getattr(settings, "REFRAME_MIN_SAMPLES_TO_STOP", 90) or 90)

    effective_fps = fps if isinstance(fps, (int, float)) and fps and fps > 0 else 30.0
    stride = max(1, int(round(effective_fps * sample_every_seconds)))

    try:
        with FaceDetector.create_from_options(options) as detector:
            for i in range(0, total_frames, stride):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if not ret:
                    break

                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                detection_result = detector.detect(mp_image)

                if detection_result.detections:
                    best_detection = max(detection_result.detections, key=lambda d: d.categories[0].score)
                    bbox = best_detection.bounding_box

                    center_x = int(bbox.origin_x + bbox.width / 2)
                    face_centers_x.append(center_x)

                    if len(face_centers_x) >= max_samples:
                        break

                if len(face_centers_x) >= min_samples_to_stop:
                    break
    finally:
        cap.release()

    face_detected = len(face_centers_x) > 0
    
    if face_detected:
        stable_center_x = int(np.median(face_centers_x))
    else:
        stable_center_x = width // 2

    crops = _calculate_crops(width, height, stable_center_x)

    return {
        "face_detected": face_detected,
        "video_resolution": f"{width}x{height}",
        "crops": crops,
        "raw_face_centers_count": len(face_centers_x)
    }


def _calculate_crops(width: int, height: int, center_x: int) -> dict:
    crops = {}

    target_h_9_16 = height
    target_w_9_16 = int(target_h_9_16 * 9 / 16)
    
    if target_w_9_16 > width:
        target_w_9_16 = width
        target_h_9_16 = int(width * 16 / 9)

    x_9_16 = center_x - (target_w_9_16 // 2)
    
    x_9_16 = max(0, x_9_16)
    x_9_16 = min(width - target_w_9_16, x_9_16)

    crops["9:16"] = {
        "x": int(x_9_16),
        "y": 0,
        "width": int(target_w_9_16),
        "height": int(target_h_9_16),
        "center_x": center_x
    }
    
    size_1_1 = min(width, height)
    x_1_1 = center_x - (size_1_1 // 2)
    x_1_1 = max(0, min(width - size_1_1, x_1_1))
    
    crops["1:1"] = {
        "x": int(x_1_1),
        "y": 0,
        "width": size_1_1,
        "height": size_1_1
    }

    return crops