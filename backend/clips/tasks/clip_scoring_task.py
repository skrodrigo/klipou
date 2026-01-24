import logging
import os
import cv2
from typing import Optional, Any
from celery import shared_task
from django.conf import settings

from ..models import Clip, Video, Transcript
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)

DEFAULT_THUMBNAIL_FRAME_RATIO = 0.20
DEFAULT_JPEG_QUALITY = 85
DEFAULT_TIMESTAMP_TOLERANCE = 0.5
DEFAULT_FALLBACK_SCORE = 70.0
DEFAULT_DOWNLOAD_TIMEOUT = 300


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


def _to_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _normalize_score_to_0_100(raw_score: float) -> float:
    try:
        score = float(raw_score)
        if score <= 10.0:
            score = score * 10.0
        return float(max(0.0, min(score, 100.0)))
    except (ValueError, TypeError):
        return 0.0


def _sanitize_filename(filename: str) -> str:
    if not isinstance(filename, str):
        return "unknown"
    
    sanitized = filename.replace("/", "_").replace("\\", "_")
    sanitized = sanitized.replace("..", "_")
    sanitized = sanitized[:255]
    
    return sanitized if sanitized else "unknown"


@shared_task(bind=True, max_retries=3)
def clip_scoring_task(self, clip_id: str, video_id: str):
    local_clip_path = None
    thumb_path = None

    try:
        logger.info(f"[clip_score] Iniciando para clip_id={clip_id}")
        
        clip = Clip.objects.get(clip_id=clip_id)
        video = Video.objects.get(video_id=video_id)
        transcript = Transcript.objects.filter(video=video).first()
        
        matched_data = None
        timestamp_tolerance = _get_config(
            "CLIP_SCORE_TIMESTAMP_TOLERANCE",
            DEFAULT_TIMESTAMP_TOLERANCE,
            float
        )
        
        if transcript and transcript.selected_clips:
            clip_start = _to_float(clip.start_time, 0.0)
            
            for candidate in transcript.selected_clips:
                if not isinstance(candidate, dict):
                    continue
                    
                candidate_start = _to_float(candidate.get("start_time"), 0.0)
                
                if abs(candidate_start - clip_start) < timestamp_tolerance:
                    matched_data = candidate
                    logger.debug(
                        f"[clip_score] Matched candidate: "
                        f"clip_start={clip_start} candidate_start={candidate_start}"
                    )
                    break
        
        if matched_data:
            raw_score = _to_float(matched_data.get("score"), 0.0)
            score_0_100 = _normalize_score_to_0_100(raw_score)
            
            clip.engagement_score = round(score_0_100, 2)
            
            title = matched_data.get("title")
            if title and isinstance(title, str) and title.strip():
                clip.title = title.strip()[:500]
            
            logger.info(
                f"[clip_score] Score from AI: {clip.engagement_score}/100 "
                f"(raw={raw_score})"
            )
        else:
            fallback_score = _get_config(
                "CLIP_SCORE_FALLBACK",
                DEFAULT_FALLBACK_SCORE,
                float
            )
            clip.engagement_score = round(float(fallback_score), 2)
            
            logger.warning(
                f"[clip_score] No AI data found for clip, "
                f"using fallback score: {clip.engagement_score}/100"
            )

        storage = R2StorageService()
        
        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp_thumbs")
        os.makedirs(temp_dir, exist_ok=True)
        
        safe_clip_id = _sanitize_filename(str(clip_id))
        local_clip_path = os.path.join(temp_dir, f"{safe_clip_id}.mp4")
        
        if not clip.storage_path:
            logger.warning("[clip_score] Clip has no storage_path, skipping thumbnail")
        else:
            download_timeout = _get_config(
                "CLIP_SCORE_DOWNLOAD_TIMEOUT",
                DEFAULT_DOWNLOAD_TIMEOUT,
                int
            )
            
            try:
                logger.debug(f"[clip_score] Downloading clip from {clip.storage_path}")
                storage.download_file(
                    clip.storage_path,
                    local_clip_path,
                    timeout=download_timeout
                )
            except Exception as download_err:
                logger.error(f"[clip_score] Download failed: {download_err}")
                raise
        
        if os.path.exists(local_clip_path):
            file_size = os.path.getsize(local_clip_path)
            
            if file_size <= 0:
                logger.warning("[clip_score] Downloaded file is empty, skipping thumbnail")
            else:
                logger.debug(f"[clip_score] Downloaded {file_size} bytes")
                
                try:
                    thumb_path = _extract_thumbnail(
                        local_clip_path,
                        temp_dir,
                        safe_clip_id
                    )
                except Exception as extract_err:
                    logger.error(f"[clip_score] Thumbnail extraction failed: {extract_err}")
                    thumb_path = None
            
                if thumb_path and os.path.exists(thumb_path):
                    try:
                        thumb_storage_path = storage.upload_thumbnail(
                            file_path=thumb_path,
                            organization_id=str(video.organization_id),
                            video_id=str(video_id),
                            filename=f"thumb_{safe_clip_id}.jpg"
                        )
                        
                        if thumb_storage_path:
                            clip.thumbnail_storage_path = thumb_storage_path
                            logger.info(f"[clip_score] Thumbnail uploaded: {thumb_storage_path}")
                        else:
                            logger.warning("[clip_score] Thumbnail upload returned empty path")
                            
                    except Exception as upload_err:
                        logger.error(f"[clip_score] Thumbnail upload failed: {upload_err}")
                else:
                    logger.warning("[clip_score] Thumbnail not extracted")

        clip.save()
        
        logger.info(
            f"[clip_score] Completed for clip_id={clip_id}: "
            f"score={clip.engagement_score} has_thumb={bool(clip.thumbnail_storage_path)}"
        )
        
        return {
            "clip_id": str(clip_id),
            "score": clip.engagement_score,
            "has_thumbnail": bool(clip.thumbnail_storage_path),
            "status": "success",
        }
    
    except Clip.DoesNotExist:
        logger.error(f"[clip_score] Clip not found: {clip_id}")
        return {"error": "Clip not found", "status": "failed"}
        
    except Video.DoesNotExist:
        logger.error(f"[clip_score] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[clip_score] Error for clip_id={clip_id}: {e}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            countdown = max(countdown, 10)
            
            logger.info(
                f"[clip_score] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                f"in {countdown}s"
            )
            raise self.retry(exc=e, countdown=countdown)
            
        return {"error": str(e)[:500], "status": "failed"}
        
    finally:
        cleanup_errors = []
        
        if local_clip_path and os.path.exists(local_clip_path):
            try:
                os.remove(local_clip_path)
                logger.debug(f"[clip_score] Removed local clip: {local_clip_path}")
            except Exception as e:
                cleanup_errors.append(f"clip: {e}")
                logger.warning(f"[clip_score] Failed to remove {local_clip_path}: {e}")
                
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
                logger.debug(f"[clip_score] Removed thumbnail: {thumb_path}")
            except Exception as e:
                cleanup_errors.append(f"thumb: {e}")
                logger.warning(f"[clip_score] Failed to remove {thumb_path}: {e}")
        
        if cleanup_errors:
            logger.warning(f"[clip_score] Cleanup errors: {', '.join(cleanup_errors)}")


def _extract_thumbnail(
    video_path: str,
    output_dir: str,
    clip_id: str
) -> Optional[str]:
    
    if not os.path.exists(video_path):
        logger.error(f"[thumbnail] Video file not found: {video_path}")
        return None
    
    file_size = os.path.getsize(video_path)
    if file_size <= 0:
        logger.error(f"[thumbnail] Video file is empty: {video_path}")
        return None

    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        logger.error(f"[thumbnail] Failed to open video: {video_path}")
        return None
    
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.debug(
            f"[thumbnail] Video info: frames={total_frames} fps={fps} "
            f"resolution={width}x{height}"
        )
        
        if total_frames <= 0:
            logger.error("[thumbnail] Video has no frames")
            return None
        
        frame_ratio = _get_config(
            "CLIP_THUMBNAIL_FRAME_RATIO",
            DEFAULT_THUMBNAIL_FRAME_RATIO,
            float
        )
        frame_ratio = float(max(0.0, min(frame_ratio, 1.0)))
        
        target_frame = int(total_frames * frame_ratio)
        target_frame = max(0, min(target_frame, total_frames - 1))
        
        logger.debug(f"[thumbnail] Extracting frame {target_frame}/{total_frames}")
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        ret, frame = cap.read()
        
        if not ret:
            logger.error(f"[thumbnail] Failed to read frame {target_frame}")
            return None
        
        if frame is None or frame.size == 0:
            logger.error("[thumbnail] Extracted frame is empty")
            return None
        
        frame_height, frame_width = frame.shape[:2]
        logger.debug(f"[thumbnail] Frame extracted: {frame_width}x{frame_height}")
        
        safe_clip_id = _sanitize_filename(str(clip_id))
        output_path = os.path.join(output_dir, f"{safe_clip_id}_thumb.jpg")
        
        jpeg_quality = _get_config(
            "CLIP_THUMBNAIL_JPEG_QUALITY",
            DEFAULT_JPEG_QUALITY,
            int
        )
        jpeg_quality = int(max(1, min(jpeg_quality, 100)))
        
        success = cv2.imwrite(
            output_path,
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        )
        
        if not success:
            logger.error(f"[thumbnail] cv2.imwrite failed for {output_path}")
            return None
        
        if not os.path.exists(output_path):
            logger.error(f"[thumbnail] Output file not created: {output_path}")
            return None
        
        thumb_size = os.path.getsize(output_path)
        if thumb_size <= 0:
            logger.error("[thumbnail] Generated thumbnail is empty")
            try:
                os.remove(output_path)
            except Exception:
                pass
            return None
        
        logger.debug(f"[thumbnail] Created: {output_path} ({thumb_size} bytes)")
        
        return output_path
        
    except Exception as e:
        logger.error(f"[thumbnail] Extraction error: {e}", exc_info=True)
        return None
        
    finally:
        cap.release()