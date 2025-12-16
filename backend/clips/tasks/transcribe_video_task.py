import logging
import os
import json
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def transcribe_video_task(self, video_id: str) -> dict:
    audio_path = None
    try:
        logger.info(f"Iniciando transcrição para video_id: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "transcribing"
        video.current_step = "transcribing"
        video.save()
        update_job_status(str(video.video_id), "transcribing", progress=35, current_step="transcribing")

        video_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        
        video_path = os.path.join(video_dir, "video_normalized.mp4")
        if not os.path.exists(video_path):
            raise Exception("Arquivo video_normalized.mp4 não encontrado")

        audio_path = _extract_audio_with_ffmpeg(video_path, video_dir)

        transcript_data = _transcribe_with_whisper(audio_path)

        json_path = os.path.join(video_dir, "transcript.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

        srt_path = os.path.join(video_dir, "transcript.srt")
        _save_srt_file(transcript_data, srt_path)

        storage = R2StorageService()
        transcript_storage_path = storage.upload_transcript(
            file_path=json_path,
            organization_id=str(video.organization_id),
            video_id=str(video.video_id),
        )

        Transcript.objects.update_or_create(
            video=video,
            defaults={
                "full_text": transcript_data.get("full_text", ""),
                "segments": transcript_data.get("segments", []),
                "language": transcript_data.get("language", "en"),
                "confidence_score": transcript_data.get("confidence_score", 0),
                "storage_path": transcript_storage_path,
            }
        )

        if os.path.exists(audio_path):
            os.remove(audio_path)

        video.last_successful_step = "transcribing"
        video.status = "analyzing"
        video.current_step = "analyzing"
        video.save()
        
        update_job_status(str(video.video_id), "analyzing", progress=40, current_step="analyzing")

        from .analyze_semantic_task import analyze_semantic_task
        analyze_semantic_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.analyze.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "language": transcript_data.get("language"),
            "words_count": len(transcript_data.get("full_text", "").split()),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro transcrição {video_id}: {str(e)}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()
            
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass

            if self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _extract_audio_with_ffmpeg(video_path: str, output_dir: str) -> str:
    audio_path = os.path.join(output_dir, "audio_temp.wav")
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    
    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return audio_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro FFmpeg áudio: {e.stderr.decode() if e.stderr else str(e)}")


def _transcribe_with_whisper(audio_path: str) -> dict:
    try:
        import whisper
        import torch
    except ImportError:
        raise Exception("Instale: pip install openai-whisper torch")

    model_size = getattr(settings, "WHISPER_MODEL", "small")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    logger.info(f"Carregando Whisper modelo '{model_size}' em '{device}'...")
    
    try:
        model = whisper.load_model(model_size, device=device)
        
        result = model.transcribe(audio_path, word_timestamps=True)
        
    except Exception as e:
        if device == "cuda":
            torch.cuda.empty_cache()
        raise Exception(f"Falha interna Whisper: {e}")

    segments = result.get("segments", [])
    full_text = result.get("text", "").strip()
    language = result.get("language", "en")

    structured_segments = []
    
    for seg in segments:
        words = []
        if "words" in seg:
            for w in seg["words"]:
                words.append({
                    "word": w["word"].strip(),
                    "start": w["start"],
                    "end": w["end"],
                    "score": w.get("probability", 0)
                })
        
        structured_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "words": words
        })

    if device == "cuda":
        del model
        torch.cuda.empty_cache()

    return {
        "full_text": full_text,
        "segments": structured_segments,
        "language": language,
        "confidence_score": 95
    }


def _save_srt_file(transcript_data: dict, srt_path: str) -> None:
    segments = transcript_data.get("segments", [])
    
    def format_time(seconds):
        millis = int((seconds % 1) * 1000)
        seconds = int(seconds)
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_time(seg["start"])
            end = format_time(seg["end"])
            text = seg["text"].replace("\n", " ")
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
