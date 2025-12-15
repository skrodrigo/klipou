"""
Task para transcrição de vídeo com Whisper.
Etapa: Transcribing
Gera transcrição com timestamps por palavra (obrigatório para legendagem).
"""

import os
import json
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript
from ..services.storage_service import R2StorageService


@shared_task(bind=True, max_retries=5)
def transcribe_video_task(self, video_id: int) -> dict:
    """
    Executa Whisper local para transcrição.
    
    Gera:
    - Transcrição completa (texto bruto com timestamps)
    - Timestamps por segmento (início/fim de cada frase)
    - Timestamps por palavra (para legendagem ASS e karaoke)
    
    Salva:
    - JSON bruto (estruturado com timestamps por palavra)
    - SRT (para compatibilidade)
    """
    try:
        video = Video.objects.get(id=video_id)
        video.status = "transcribing"
        video.current_step = "transcribing"
        video.save()

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Arquivo normalizado da etapa anterior
        video_path = os.path.join(output_dir, "video_normalized.mp4")

        if not os.path.exists(video_path):
            raise Exception("Arquivo de vídeo normalizado não encontrado")

        # Extrai áudio
        audio_path = _extract_audio_with_ffmpeg(video_path, output_dir)

        # Transcreve com Whisper
        transcript_data = _transcribe_with_whisper(audio_path, output_dir)

        # Salva transcrição em JSON
        json_path = os.path.join(output_dir, "transcript.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

        # Salva transcrição em SRT
        srt_path = os.path.join(output_dir, "transcript.srt")
        _save_srt_file(transcript_data, srt_path)

        # Faz upload para R2
        storage = R2StorageService()
        transcript_storage_path = storage.upload_transcript(
            file_path=json_path,
            organization_id=str(video.organization_id),
            video_id=str(video.video_id),
        )

        # Cria registro de Transcript no banco
        Transcript.objects.create(
            video=video,
            full_text=transcript_data.get("full_text", ""),
            segments=transcript_data.get("segments", []),
            language=transcript_data.get("language", "en"),
            confidence_score=transcript_data.get("confidence_score", 0),
            storage_path=transcript_storage_path,
        )

        # Atualiza vídeo
        video.last_successful_step = "transcribing"
        video.save()

        return {
            "video_id": video_id,
            "status": "transcribing",
            "language": transcript_data.get("language"),
            "confidence_score": transcript_data.get("confidence_score"),
            "segments_count": len(transcript_data.get("segments", [])),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "transcribing"
        video.error_code = "TRANSCRIPTION_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _extract_audio_with_ffmpeg(video_path: str, output_dir: str) -> str:
    """Extrai faixa de áudio do vídeo em WAV mono 16kHz para Whisper."""
    audio_path = os.path.join(output_dir, "audio_for_whisper.wav")
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 600))

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ffmpeg_timeout,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg falhou ao extrair áudio: {e}")

    if not os.path.exists(audio_path):
        raise Exception("Arquivo de áudio não foi criado")

    return audio_path


def _transcribe_with_whisper(audio_path: str, output_dir: str) -> dict:
    """Transcreve áudio com Whisper e retorna dados estruturados."""
    try:
        import whisper
    except ImportError:
        raise Exception("Whisper não está instalado. Adicione 'openai-whisper' às dependências")

    model_name = getattr(settings, "WHISPER_MODEL", "base")
    device = getattr(settings, "WHISPER_DEVICE", "cpu")

    try:
        model = whisper.load_model(model_name, device=device)
        result = model.transcribe(audio_path)
    except Exception as e:
        raise Exception(f"Whisper falhou ao transcrever: {e}")

    # Extrai dados estruturados
    segments = result.get("segments", [])
    language = result.get("language", "en")

    # Constrói texto completo
    full_text = " ".join([seg.get("text", "").strip() for seg in segments])

    # Estrutura segmentos com timestamps por palavra
    structured_segments = []
    for seg in segments:
        segment_data = {
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": seg.get("text", "").strip(),
            "words": [],
        }

        # Se disponível, extrai timestamps por palavra
        if "words" in seg:
            segment_data["words"] = seg["words"]

        structured_segments.append(segment_data)

    # Calcula confidence score (média de confiança dos segmentos)
    confidence_scores = [seg.get("confidence", 1.0) for seg in segments if "confidence" in seg]
    confidence_score = int(sum(confidence_scores) / len(confidence_scores) * 100) if confidence_scores else 95

    return {
        "full_text": full_text,
        "segments": structured_segments,
        "language": language,
        "confidence_score": confidence_score,
    }


def _save_srt_file(transcript_data: dict, srt_path: str) -> None:
    """Salva transcrição em formato SRT."""
    segments = transcript_data.get("segments", [])

    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, 1):
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "").strip()

            if not text:
                continue

            start_ts = _seconds_to_srt_time(start)
            end_ts = _seconds_to_srt_time(end)

            f.write(f"{idx}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{text}\n\n")


def _seconds_to_srt_time(seconds: float) -> str:
    """Converte segundos para formato SRT HH:MM:SS,mmm."""
    total_millis = int(round(seconds * 1000))
    hours, rem = divmod(total_millis, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
