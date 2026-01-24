import logging
import os
import json
import subprocess
import gc
import torch
import time
from celery import shared_task
from django.conf import settings
from google import genai
from google.genai import types

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)

_model_cache = None
_gemini_client = None


def _should_use_cuda() -> bool:
    forced = getattr(settings, "WHISPER_DEVICE", None)
    if not (isinstance(forced, str) and forced.strip()):
        return False

    forced_norm = forced.strip().lower()
    if forced_norm != "cuda":
        return False

    if not torch.cuda.is_available():
        return False

    try:
        torch.zeros(1, device="cuda")
    except Exception:
        return False

    cudnn_ok = True
    try:
        cudnn_ok = bool(torch.backends.cudnn.is_available())
    except Exception:
        cudnn_ok = False

    return cudnn_ok


def _get_whisper_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("Biblioteca 'faster-whisper' não encontrada. Instale: pip install faster-whisper")

    model_size = getattr(settings, "WHISPER_MODEL", "small")
    local_model_dir = getattr(settings, "WHISPER_MODEL_DIR", None)

    for noisy_logger in ("httpx", "httpcore", "huggingface_hub"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    device = "cuda" if _should_use_cuda() else "cpu"

    if device == "cuda":
        fp16_enabled = bool(getattr(settings, "WHISPER_FP16", True))
        compute_type = "float16" if fp16_enabled else "int8_float16"

        override = getattr(settings, "WHISPER_CUDA_COMPUTE_TYPE", None)
        if isinstance(override, str) and override.strip():
            compute_type = override.strip()
    else:
        compute_type = "int8"

    model_source = local_model_dir or model_size

    logger.info(
        "[whisper] loading model=%s device=%s compute_type=%s%s",
        model_size,
        device,
        compute_type,
        f" | model_dir: {local_model_dir}" if local_model_dir else "",
    )

    lock_dir = getattr(settings, "WHISPER_LOCK_DIR", getattr(settings, "BASE_DIR", "/tmp"))
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, f"faster_whisper_{str(model_size).replace('/', '_')}.lock")

    start_wait = time.time()
    timeout_s = int(getattr(settings, "WHISPER_INIT_LOCK_TIMEOUT", 600) or 600)
    have_lock = False
    while not have_lock:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            have_lock = True
        except FileExistsError:
            if time.time() - start_wait > timeout_s:
                raise TimeoutError(f"Timeout aguardando lock do Whisper em {lock_path}")
            time.sleep(0.25)

    try:
        _model_cache = WhisperModel(
            model_source,
            device=device,
            compute_type=compute_type,
        )
    except Exception as e:
        raise RuntimeError(f"Falha interna Faster-Whisper: {e}")
    finally:
        if have_lock:
            try:
                os.remove(lock_path)
            except OSError:
                pass
    return _model_cache


@shared_task(bind=True, max_retries=5, acks_late=False)
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
            raise FileNotFoundError("Arquivo video_normalized.mp4 não encontrado")

        update_job_status(str(video.video_id), "transcribing", progress=35, current_step="extracting_audio")
        audio_path = _extract_audio_with_ffmpeg(video_path, video_dir)

        update_job_status(str(video.video_id), "transcribing", progress=35, current_step="whisper_transcribing")
        transcript_data = _transcribe_with_whisper(audio_path, job_video_id=str(video.video_id))

        if bool(getattr(settings, "GEMINI_REFINE_WHISPER_TRANSCRIPT", False)):
            try:
                transcript_data = _refine_transcript_with_gemini(transcript_data)
            except Exception as e:
                logger.warning(f"[transcribe] Gemini refine falhou; seguindo com Whisper original: {e}")

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

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        video.last_successful_step = "transcribing"
        video.status = "analyzing"
        video.current_step = "analyzing"
        video.save()

        update_job_status(str(video.video_id), "analyzing", progress=40, current_step="analyzing")

        from .analyze_semantic_task import analyze_semantic_task
        analyze_semantic_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.analyze.{get_plan_tier(org.plan)}",
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

            # Limpeza de memória mesmo no erro
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            if self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _extract_audio_with_ffmpeg(video_path: str, output_dir: str) -> str:
    audio_path = os.path.join(output_dir, "audio_temp.wav")
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    max_seconds = getattr(settings, "WHISPER_MAX_AUDIO_SECONDS", None)

    cmd = [
        ffmpeg_path, "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", video_path,
        "-map", "0:a:0?",
        "-vn",
        "-err_detect", "ignore_err",
        "-fflags", "+discardcorrupt",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]

    if isinstance(max_seconds, (int, float)) and max_seconds and max_seconds > 0:
        cmd.insert(-1, str(float(max_seconds)))
        cmd.insert(-1, "-t")

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Erro FFmpeg áudio: {e.stderr.decode() if e.stderr else str(e)}")


def _transcribe_with_whisper(audio_path: str, job_video_id: str) -> dict:
    global _model_cache
    model = _get_whisper_model()

    whisper_word_timestamps = bool(getattr(settings, "WHISPER_WORD_TIMESTAMPS", True))
    beam_size = int(getattr(settings, "WHISPER_BEAM_SIZE", 5))

    def _run(model_to_use):
        return model_to_use.transcribe(
            audio_path,
            beam_size=beam_size,
            word_timestamps=whisper_word_timestamps,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

    try:
        segments_generator, info = _run(model)
    except Exception as e:
        msg = str(e)
        is_cuda_oom = "CUDA" in msg and ("out of memory" in msg.lower() or "cublas" in msg.lower())
        if is_cuda_oom and getattr(model, "device", None) == "cuda":
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            from faster_whisper import WhisperModel
            model_size = getattr(settings, "WHISPER_MODEL", "small")
            local_model_dir = getattr(settings, "WHISPER_MODEL_DIR", None)
            model_source = local_model_dir or model_size
            _model_cache = WhisperModel(model_source, device="cpu", compute_type="int8")
            segments_generator, info = _run(_model_cache)
        else:
            raise RuntimeError(f"Falha interna Faster-Whisper: {e}")

    structured_segments = []
    full_text_parts = []
    last_heartbeat = time.time()
    for seg in segments_generator:
        if time.time() - last_heartbeat >= 20:
            try:
                update_job_status(job_video_id, "transcribing", progress=35, current_step=f"whisper_running_{len(structured_segments)}")
            except Exception:
                pass
            last_heartbeat = time.time()

        text_stripped = seg.text.strip()
        if text_stripped:
            full_text_parts.append(text_stripped)

        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    {
                        "word": w.word.strip(),
                        "start": w.start,
                        "end": w.end,
                        "score": w.probability,
                    }
                )

        structured_segments.append(
            {
                "start": seg.start,
                "end": seg.end,
                "text": text_stripped,
                "words": words,
            }
        )

    return {
        "full_text": " ".join(full_text_parts).strip(),
        "segments": structured_segments,
        "language": info.language,
        "confidence_score": int(info.language_probability * 100),
    }


def _refine_transcript_with_gemini(transcript_data: dict) -> dict:
    client = _get_gemini_client()

    segments = transcript_data.get("segments") or []
    language = (transcript_data.get("language") or "").lower()

    max_segments = int(getattr(settings, "GEMINI_REFINE_MAX_SEGMENTS", 120) or 120)

    input_segments = []
    for i, seg in enumerate(segments[:max_segments]):
        input_segments.append(
            {
                "i": i,
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg.get("text", ""),
            }
        )

    response_schema = {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "language": {"type": "string"},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["i", "text"],
                },
            },
        },
        "required": ["domain", "language", "segments"],
    }

    base_prompt_pt = """
            Você é um revisor de transcrições expert (Português).

            Objetivo:
            - Primeiro inferir o CONTEXTO/DOMÍNIO da conversa (ex: negócios, saúde, estudos, espaço, medicina, produtividade, programação, marketing, finanças, fitness, etc.).
            - Em seguida, corrigir termos que o Whisper errou por causa de gírias, jargões, palavreado, metáforas ou nomes próprios.

            Regras críticas:
            1) NÃO altere timestamps. Eles já estão corretos. Você só pode reescrever o campo "text".
            2) Preserve o sentido original e o tom. Não censure palavrões; apenas corrija grafia/termos.
            3) Seja conservador: se não tiver certeza da correção, mantenha o original.
            4) Não invente conteúdo que não foi falado.
            5) Retorne SOMENTE JSON conforme o schema.

            Entrada: lista de segmentos com índice i e seus textos.
            Saída: para cada i, retorne "text" revisado.
            """

    base_prompt_en = """
            You are an expert transcript editor.

            Goal:
            - First infer the conversation domain/context (business, health, studies, space, medicine, productivity, programming, etc.).
            - Then fix misrecognized words caused by slang, jargon, metaphors, or proper nouns.

            Critical rules:
            1) Do NOT change timestamps. Only rewrite the "text" fields.
            2) Preserve meaning and tone. Do not censor.
            3) Be conservative: if unsure, keep the original.
            4) Do not invent content.
            5) Return ONLY JSON matching the schema.
            """

    prompt = base_prompt_pt if language.startswith("pt") else base_prompt_en
    payload = {
        "segments": input_segments,
    }

    model_name = getattr(settings, "GEMINI_REFINE_MODEL", "gemini-2.5-flash-lite")
    response = client.models.generate_content(
        model=f'models/{model_name}',
        contents=f"{prompt}\n\nSEGMENTS JSON:\n{json.dumps(payload, ensure_ascii=False)}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=float(getattr(settings, "GEMINI_REFINE_TEMPERATURE", 0.2) or 0.2),
        ),
    )

    refined = json.loads(response.text or "{}")
    refined_segments = refined.get("segments") or []
    by_i = {int(s.get("i")): (s.get("text") or "") for s in refined_segments if s.get("i") is not None}

    out_segments = list(segments)
    for i in range(min(len(segments[:max_segments]), len(out_segments))):
        new_text = by_i.get(i)
        if isinstance(new_text, str) and new_text.strip():
            out_segments[i] = {
                **out_segments[i],
                "text": new_text.strip(),
            }

    full_text = " ".join([(s.get("text") or "").strip() for s in out_segments]).strip()
    return {
        **transcript_data,
        "segments": out_segments,
        "full_text": full_text,
        "refine_meta": {
            "provider": "gemini",
            "model": model_name,
            "domain": refined.get("domain"),
            "language": refined.get("language") or transcript_data.get("language"),
            "segments_refined": len(out_segments[:max_segments]),
        },
    }


def _get_gemini_client():
    global _gemini_client
    if _gemini_client:
        return _gemini_client

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


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