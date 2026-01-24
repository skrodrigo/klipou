import logging
import os
from typing import Optional, Dict, Any, List
import numpy as np
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE = 0.6
DEFAULT_SAMPLE_EVERY_SECONDS = 1.0
DEFAULT_MAX_SAMPLES = 240
DEFAULT_MIN_SAMPLES_TO_STOP = 90
DEFAULT_FALLBACK_FPS = 30.0
DEFAULT_TARGET_ASPECT = "9:16"
DEFAULT_OUTLIER_TRIM_RATIO = 0.10

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None


def _get_config(key: str, default: Any, type_cast=None) -> Any:
    try:
        val = getattr(settings, key, default)
        if val is None:
            return default
        if type_cast:
            return type_cast(val)
        return val
    except (ValueError, TypeError):
        logger.warning(f"Invalid config value for {key}, using default: {default}")
        return default


def _safe_update_job_status(
    video_id: str,
    status: str,
    *,
    progress: Optional[int] = None,
    current_step: Optional[str] = None
):
    try:
        update_job_status(video_id, status, progress=progress, current_step=current_step)
    except Exception as e:
        logger.warning(f"[reframe] update_job_status failed for {video_id}: {e}")


@shared_task(bind=True, max_retries=3)
def reframe_video_task(self, video_id: str) -> dict:
    video = None
    
    try:
        logger.info(f"[reframe] Iniciando para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "reframing"
        video.current_step = "reframing"
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "reframing",
            progress=80,
            current_step="reframing"
        )

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise ValueError("Transcrição não encontrada")

        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        input_path = os.path.join(video_dir, "video_normalized.mp4")

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Vídeo normalizado não encontrado: {input_path}")

        reframe_data = _detect_smart_crop(input_path)

        transcript.reframe_data = reframe_data
        transcript.save()

        logger.info(
            f"[reframe] Concluído: face_detected={reframe_data.get('face_detected')} "
            f"samples={reframe_data.get('raw_face_centers_count')}"
        )

        video.last_successful_step = "reframing"
        video.status = "clipping"
        video.current_step = "clipping"
        video.save()

        _safe_update_job_status(
            str(video.video_id),
            "clipping",
            progress=82,
            current_step="clipping"
        )
        
        from .caption_clips_task import caption_clips_task
        caption_clips_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.clip.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "face_detected": reframe_data.get("face_detected"),
            "crop_center_x": reframe_data.get("crops", {}).get("9:16", {}).get("center_x"),
            "status": "success",
        }

    except Video.DoesNotExist:
        logger.error(f"[reframe] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[reframe] Error for video_id={video_id}: {e}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.error_message = str(e)[:500]
            video.save()

            _safe_update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="reframing"
            )

        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(
                f"[reframe] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                f"in {countdown}s"
            )
            raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e)[:500], "status": "failed"}


def _detect_smart_crop(video_path: str) -> Dict[str, Any]:
    
    if cv2 is None or mp is None:
        missing = []
        if cv2 is None:
            missing.append("opencv-python")
        if mp is None:
            missing.append("mediapipe")
        raise ImportError(
            f"Dependências ausentes: {', '.join(missing)}. "
            f"Instale com: pip install {' '.join(missing)}"
        )

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(
            f"[reframe] Video: {width}x{height} fps={fps} frames={total_frames}"
        )

        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid video dimensions: {width}x{height}")

        if total_frames <= 0:
            raise ValueError("Video has no frames")

        model_path = _get_config("MEDIAPIPE_FACE_MODEL_PATH", None, str)
        
        if not model_path:
            default_path = os.path.join(
                settings.BASE_DIR,
                "assets",
                "blaze_face_short_range.tflite"
            )
            if os.path.exists(default_path):
                model_path = default_path

        if not model_path or not os.path.exists(model_path):
            logger.warning(
                f"[reframe] Face model not found at {model_path}, "
                f"using frame center"
            )
            cap.release()
            
            center_x = width // 2
            crops = _calculate_crops(width, height, center_x)
            
            return {
                "face_detected": False,
                "video_resolution": f"{width}x{height}",
                "crops": crops,
                "raw_face_centers_count": 0,
                "fallback_reason": "model_not_found",
            }

        min_confidence = _get_config(
            "REFRAME_MIN_DETECTION_CONFIDENCE",
            DEFAULT_MIN_CONFIDENCE,
            float
        )
        min_confidence = float(max(0.0, min(min_confidence, 1.0)))

        FaceDetector = mp.tasks.vision.FaceDetector
        FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        BaseOptions = mp.tasks.BaseOptions

        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            min_detection_confidence=min_confidence,
            running_mode=VisionRunningMode.IMAGE
        )

        face_centers_x: List[int] = []

        sample_every_s = _get_config(
            "REFRAME_SAMPLE_EVERY_SECONDS",
            DEFAULT_SAMPLE_EVERY_SECONDS,
            float
        )
        sample_every_s = float(max(0.1, sample_every_s))
        
        max_samples = _get_config(
            "REFRAME_MAX_FACE_SAMPLES",
            DEFAULT_MAX_SAMPLES,
            int
        )
        max_samples = int(max(1, max_samples))
        
        min_samples_to_stop = _get_config(
            "REFRAME_MIN_SAMPLES_TO_STOP",
            DEFAULT_MIN_SAMPLES_TO_STOP,
            int
        )
        min_samples_to_stop = int(max(1, min(min_samples_to_stop, max_samples)))

        effective_fps = fps if isinstance(fps, (int, float)) and fps > 0 else DEFAULT_FALLBACK_FPS
        effective_fps = float(max(1.0, effective_fps))
        
        stride = int(round(effective_fps * sample_every_s))
        stride = int(max(1, stride))

        logger.info(
            f"[reframe] Sampling: stride={stride} max_samples={max_samples} "
            f"min_to_stop={min_samples_to_stop}"
        )

        frames_processed = 0
        
        with FaceDetector.create_from_options(options) as detector:
            for frame_idx in range(0, total_frames, stride):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    logger.debug(f"[reframe] Failed to read frame {frame_idx}")
                    break

                if frame is None or frame.size == 0:
                    logger.debug(f"[reframe] Empty frame at {frame_idx}")
                    continue

                frames_processed += 1

                try:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb_frame
                    )
                    detection_result = detector.detect(mp_image)
                except Exception as detection_err:
                    logger.warning(f"[reframe] Detection failed at frame {frame_idx}: {detection_err}")
                    continue

                if detection_result.detections:
                    best_detection = max(
                        detection_result.detections,
                        key=lambda d: d.categories[0].score
                    )
                    
                    bbox = best_detection.bounding_box
                    
                    try:
                        center_x = int(bbox.origin_x + bbox.width / 2)
                        
                        if 0 <= center_x < width:
                            face_centers_x.append(center_x)
                        else:
                            logger.debug(
                                f"[reframe] Face center {center_x} out of bounds [0, {width})"
                            )
                    except (AttributeError, TypeError) as e:
                        logger.warning(f"[reframe] Invalid bbox at frame {frame_idx}: {e}")
                        continue

                    if len(face_centers_x) >= max_samples:
                        logger.info(f"[reframe] Reached max_samples ({max_samples})")
                        break

                if len(face_centers_x) >= min_samples_to_stop:
                    logger.info(
                        f"[reframe] Reached min_samples_to_stop "
                        f"({min_samples_to_stop}), stopping early"
                    )
                    break

        logger.info(
            f"[reframe] Processed {frames_processed} frames, "
            f"detected {len(face_centers_x)} faces"
        )

    finally:
        cap.release()

    face_detected = len(face_centers_x) > 0
    
    if face_detected:
        stable_center_x = _calculate_stable_center(face_centers_x, width)
    else:
        stable_center_x = width // 2
        logger.info("[reframe] No faces detected, using frame center")

    crops = _calculate_crops(width, height, stable_center_x)

    return {
        "face_detected": face_detected,
        "video_resolution": f"{width}x{height}",
        "crops": crops,
        "raw_face_centers_count": len(face_centers_x),
    }


def _calculate_stable_center(
    face_centers: List[int],
    video_width: int
) -> int:
    
    if not face_centers:
        return video_width // 2

    sorted_centers = sorted(int(x) for x in face_centers if isinstance(x, (int, float)))
    
    if not sorted_centers:
        return video_width // 2

    trim_ratio = _get_config(
        "REFRAME_OUTLIER_TRIM_RATIO",
        DEFAULT_OUTLIER_TRIM_RATIO,
        float
    )
    trim_ratio = float(max(0.0, min(trim_ratio, 0.5)))

    if len(sorted_centers) >= 10:
        trim_count = max(1, int(len(sorted_centers) * trim_ratio))
        
        if len(sorted_centers) > 2 * trim_count:
            sorted_centers = sorted_centers[trim_count:-trim_count]
            logger.debug(
                f"[reframe] Trimmed {trim_count} outliers from each side, "
                f"remaining: {len(sorted_centers)}"
            )

    median_center = int(np.median(sorted_centers))
    
    clamped_center = int(max(0, min(median_center, video_width - 1)))
    
    if clamped_center != median_center:
        logger.warning(
            f"[reframe] Center clamped from {median_center} to {clamped_center} "
            f"(width={video_width})"
        )
    
    return clamped_center


def _calculate_crops(
    width: int,
    height: int,
    center_x: int
) -> Dict[str, Dict[str, int]]:
    
    crops: Dict[str, Dict[str, int]] = {}

    target_aspect = _get_config("REFRAME_TARGET_ASPECT", DEFAULT_TARGET_ASPECT, str)
    
    try:
        aspect_parts = target_aspect.split(":")
        if len(aspect_parts) != 2:
            raise ValueError("Invalid aspect ratio format")
            
        aspect_w = float(aspect_parts[0])
        aspect_h = float(aspect_parts[1])
        
        if aspect_w <= 0 or aspect_h <= 0:
            raise ValueError("Aspect ratio must be positive")
            
    except (ValueError, IndexError) as e:
        logger.warning(f"[reframe] Invalid aspect ratio '{target_aspect}': {e}, using 9:16")
        aspect_w, aspect_h = 9.0, 16.0

    target_height = height
    target_width = int(target_height * (aspect_w / aspect_h))
    
    if target_width > width:
        target_width = width
        target_height = int(width * (aspect_h / aspect_w))

    target_width = int(max(1, min(target_width, width)))
    target_height = int(max(1, min(target_height, height)))

    crop_x = center_x - (target_width // 2)
    
    crop_x = int(max(0, crop_x))
    crop_x = int(min(width - target_width, crop_x))

    crop_y = 0
    
    enable_vertical_centering = _get_config("REFRAME_ENABLE_VERTICAL_CENTERING", False, bool)
    
    if enable_vertical_centering and target_height < height:
        crop_y = (height - target_height) // 2
        crop_y = int(max(0, min(crop_y, height - target_height)))

    crops["9:16"] = {
        "x": int(crop_x),
        "y": int(crop_y),
        "width": int(target_width),
        "height": int(target_height),
        "center_x": int(center_x),
    }
    
    enable_square_crop = _get_config("REFRAME_ENABLE_SQUARE_CROP", True, bool)
    
    if enable_square_crop:
        square_size = min(width, height)
        square_x = center_x - (square_size // 2)
        square_x = int(max(0, min(width - square_size, square_x)))
        
        square_y = 0
        if enable_vertical_centering and square_size < height:
            square_y = (height - square_size) // 2
            square_y = int(max(0, min(square_y, height - square_size)))
        
        crops["1:1"] = {
            "x": int(square_x),
            "y": int(square_y),
            "width": int(square_size),
            "height": int(square_size),
        }

    logger.debug(f"[reframe] Calculated crops: {crops}")
    
    return crops