import logging
import os
import json
import subprocess
import gc
import torch
import time
import threading
from celery import shared_task
from django.conf import settings
from google.genai import types

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status
from ..services.storage_service import R2StorageService
from ..services.gemini_utils import get_gemini_client, enforce_gemini_rate_limit

logger = logging.getLogger(__name__)

_model_cache = None
_model_cache_device = None
_model_cache_compute_type = None
_model_cache_lock = threading.Lock()


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _get_audio_duration_seconds(audio_path: str) -> float:
    ffprobe_path = getattr(settings, "FFPROBE_PATH", None) or getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        out = _run_subprocess(cmd).stdout.strip()
        return float(out or 0)
    except Exception:
        return 0.0


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

    cudnn_ok = False
    try:
        cudnn_ok = bool(torch.backends.cudnn.is_available())
    except Exception:
        cudnn_ok = False

    return cudnn_ok


def _should_empty_cuda_cache(model_device: str | None) -> bool:
    if model_device != "cuda":
        return False
    return bool(torch.cuda.is_available())


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
        if not audio_path or not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 0:
            raise RuntimeError("Falha ao extrair áudio: arquivo ausente ou vazio")

        dur = float(_get_audio_duration_seconds(audio_path) or 0)
        if dur <= 0:
            raise RuntimeError("Falha ao extrair áudio: duração inválida")
        min_audio_seconds = float(getattr(settings, "WHISPER_MIN_AUDIO_SECONDS", 0.5) or 0.5)
        if dur < min_audio_seconds:
            raise RuntimeError("Falha ao extrair áudio: duração muito curta")

        update_job_status(str(video.video_id), "transcribing", progress=35, current_step="whisper_transcribing")
        transcript_data = _transcribe_with_whisper(audio_path, job_video_id=str(video.video_id))

        if bool(getattr(settings, "GEMINI_REFINE_WHISPER_TRANSCRIPT", False)):
            try:
                enforce_gemini_rate_limit(organization_id=str(video.organization_id), kind="refine")
                transcript_data = _refine_transcript_with_gemini(transcript_data)
            except Exception as e:
                logger.warning(f"[transcribe] Gemini refine falhou; seguindo com Whisper original: {e}")

        json_path = os.path.join(video_dir, "transcript.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

        srt_path = os.path.join(video_dir, "transcript.srt")
        write_srt = bool(getattr(settings, "WHISPER_WRITE_SRT", True))
        if write_srt:
            _save_srt_file(transcript_data, srt_path)

        storage = R2StorageService()
        transcript_storage_path = storage.upload_transcript(
            file_path=json_path,
            organization_id=str(video.organization_id),
            video_id=str(video.video_id),
        )
        if not transcript_storage_path or not isinstance(transcript_storage_path, str):
            raise RuntimeError("Falha ao salvar transcrição no storage")

        srt_storage_path = None
        if write_srt and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            try:
                srt_storage_path = storage.upload_transcript_srt(
                    file_path=srt_path,
                    organization_id=str(video.organization_id),
                    video_id=str(video.video_id),
                )
            except Exception as e:
                logger.warning(f"[transcribe] upload srt falhou: {e}")

        caption_files = []
        if isinstance(srt_storage_path, str) and srt_storage_path:
            caption_files = [
                {
                    "kind": "srt",
                    "path": srt_storage_path,
                    "filename": "transcript.srt",
                }
            ]

        Transcript.objects.update_or_create(
            video=video,
            defaults={
                "full_text": transcript_data.get("full_text", ""),
                "segments": transcript_data.get("segments", []),
                "language": transcript_data.get("language", "en"),
                "confidence_score": transcript_data.get("confidence_score", 0),
                "storage_path": transcript_storage_path,
                "caption_files": caption_files,
            }
        )

        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

        gc.collect()
        if _should_empty_cuda_cache(getattr(_model_cache, "device", _model_cache_device)):
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

            gc.collect()
            if _should_empty_cuda_cache(getattr(_model_cache, "device", _model_cache_device)):
                torch.cuda.empty_cache()

            msg = str(e)
            permanent = (
                isinstance(e, FileNotFoundError)
                or "não encontrado" in msg.lower()
                or "not found" in msg.lower()
                or "GEMINI_API_KEY" in msg
                or "faster-whisper" in msg.lower()
                or "ffmpeg" in msg.lower()
                or "ffprobe" in msg.lower()
                or "invalid device" in msg.lower()
                or "unsupported" in msg.lower()
            )

            if not permanent and self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)

            return {"error": str(e), "status": "failed"}


def _extract_audio_with_ffmpeg(video_path: str, output_dir: str) -> str:
    audio_path = os.path.join(output_dir, "audio_temp.wav")
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    max_seconds = getattr(settings, "WHISPER_MAX_AUDIO_SECONDS", None)

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
    ]

    cmd.extend(
        [
            "-i",
            video_path,
        ]
    )

    if isinstance(max_seconds, (int, float)) and max_seconds and max_seconds > 0:
        cmd.extend(["-t", str(float(max_seconds))])

    sample_rate = int(getattr(settings, "WHISPER_AUDIO_SAMPLE_RATE", 16000) or 16000)
    channels = int(getattr(settings, "WHISPER_AUDIO_CHANNELS", 1) or 1)

    cmd.extend(
        [
            "-map",
            "0:a:0?",
            "-vn",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+discardcorrupt",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            audio_path,
        ]
    )

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Erro FFmpeg áudio: {e.stderr.decode() if e.stderr else str(e)}")


def _transcribe_with_whisper(audio_path: str, job_video_id: str) -> dict:
    global _model_cache, _model_cache_device, _model_cache_compute_type
    model = _get_whisper_model()

    whisper_word_timestamps = bool(getattr(settings, "WHISPER_WORD_TIMESTAMPS", True))
    beam_size = int(getattr(settings, "WHISPER_BEAM_SIZE", 5))
    vad_min_silence_ms = int(getattr(settings, "WHISPER_VAD_MIN_SILENCE_MS", 500) or 500)

    def _run(model_to_use):
        return model_to_use.transcribe(
            audio_path,
            beam_size=beam_size,
            word_timestamps=whisper_word_timestamps,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=vad_min_silence_ms),
        )

    try:
        segments_generator, info = _run(model)
    except Exception as e:
        msg = str(e)
        cuda_related = ("cuda" in msg.lower()) or ("cudnn" in msg.lower())
        if cuda_related:
            logger.warning(f"[whisper] CUDA error, switching to CPU: {e}")
            try:
                from faster_whisper import WhisperModel
                model_size = getattr(settings, "WHISPER_MODEL", "small")
                local_model_dir = getattr(settings, "WHISPER_MODEL_DIR", None)
                model_source = local_model_dir or model_size
                cpu_model = WhisperModel(model_source, device="cpu", compute_type="int8")
                with _model_cache_lock:
                    _model_cache = cpu_model
                    _model_cache_device = "cpu"
                    _model_cache_compute_type = "int8"
                segments_generator, info = _run(cpu_model)
            except Exception as inner:
                raise RuntimeError(f"Falha interna Faster-Whisper: {inner}")
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
                logger.warning("[transcribe] heartbeat update_job_status failed", exc_info=True)
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
    client = get_gemini_client()

    segments = transcript_data.get("segments") or []
    language = (transcript_data.get("language") or "").lower()

    max_segments = int(getattr(settings, "GEMINI_REFINE_MAX_SEGMENTS", 120) or 120)
    batch_size = int(getattr(settings, "GEMINI_REFINE_BATCH_SIZE", 120) or 120)
    batch_size = int(max(10, min(batch_size, max_segments)))

    max_seconds = float(getattr(settings, "GEMINI_REFINE_MAX_SECONDS", 300.0) or 300.0)
    total_seconds = 0.0

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

    base_prompt_pt = (
            "Você é um revisor de transcrições expert (Português).\n\n"
            "Objetivo:\n"
            "- Primeiro inferir o CONTEXTO/DOMÍNIO da conversa (ex: negócios, saúde, estudos, espaço, medicina, produtividade, programação, marketing, finanças, fitness, etc.).\n"
            "- Em seguida, corrigir termos que o Whisper errou por causa de gírias, jargões, palavreado, metáforas ou nomes próprios.\n\n"
            "Regras críticas:\n"
            "1) NÃO altere timestamps. Eles já estão corretos. Você só pode reescrever o campo \"text\".\n"
            "2) Preserve o sentido original e o tom. Não censure palavrões; apenas corrija grafia/termos.\n"
            "3) Seja conservador: se não tiver certeza da correção, mantenha o original.\n"
            "4) Não invente conteúdo que não foi falado.\n"
            "5) Retorne SOMENTE JSON conforme o schema.\n\n"
            "Entrada: lista de segmentos com índice i e seus textos.\n"
            "Saída: para cada i, retorne \"text\" revisado."
    )

    base_prompt_en = (
            "You are an expert transcript editor.\n\n"
            "Goal:\n"
            "- First infer the conversation domain/context (business, health, studies, space, medicine, productivity, programming, etc.).\n"
            "- Then fix misrecognized words caused by slang, jargon, metaphors, or proper nouns.\n\n"
            "Critical rules:\n"
            "1) Do NOT change timestamps. Only rewrite the \"text\" fields.\n"
            "2) Preserve meaning and tone. Do not censor.\n"
            "3) Be conservative: if unsure, keep the original.\n"
            "4) Do not invent content.\n"
            "5) Return ONLY JSON matching the schema."
    )

    prompt = base_prompt_pt if language.startswith("pt") else base_prompt_en
    model_name = getattr(settings, "GEMINI_REFINE_MODEL", "gemini-2.5-flash-lite")
    temperature = float(getattr(settings, "GEMINI_REFINE_TEMPERATURE", 0.2) or 0.2)

    out_segments = list(segments)

    refined_domain = None
    refined_language = None
    refined_count = 0

    total = 0
    for i, seg in enumerate(out_segments):
        if total >= max_segments:
            break
        try:
            seg_d = float(seg.get("end") or 0) - float(seg.get("start") or 0)
        except Exception:
            seg_d = 0.0
        if seg_d < 0:
            seg_d = 0.0
        if total_seconds + seg_d > max_seconds:
            break
        total_seconds += seg_d
        total = i + 1

    total = int(min(total, len(out_segments), max_segments))
    for start_idx in range(0, total, batch_size):
        input_segments = []
        for i in range(start_idx, min(start_idx + batch_size, total)):
            seg = out_segments[i]
            input_segments.append(
                {
                    "i": i,
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text", ""),
                }
            )

        payload = {"segments": input_segments}

        response = client.models.generate_content(
            model=f"models/{model_name}",
            contents=f"{prompt}\n\nSEGMENTS JSON:\n{json.dumps(payload, ensure_ascii=False)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
            ),
        )

        refined = json.loads(response.text or "{}")
        refined_domain = refined_domain or refined.get("domain")
        refined_language = refined_language or refined.get("language")

        refined_segments = refined.get("segments") or []
        by_i = {int(s.get("i")): (s.get("text") or "") for s in refined_segments if s.get("i") is not None}

        for i in range(start_idx, min(start_idx + batch_size, total)):
            new_text = by_i.get(i)
            if isinstance(new_text, str) and new_text.strip():
                out_segments[i] = {
                    **out_segments[i],
                    "text": new_text.strip(),
                }
                refined_count += 1

    full_text = " ".join([(s.get("text") or "").strip() for s in out_segments]).strip()
    return {
        **transcript_data,
        "segments": out_segments,
        "full_text": full_text,
        "refine_meta": {
            "provider": "gemini",
            "model": model_name,
            "domain": refined_domain,
            "language": refined_language or transcript_data.get("language"),
            "segments_refined": int(total),
            "segments_rewritten": int(refined_count),
        },
    }


def _get_whisper_model():
    global _model_cache, _model_cache_device, _model_cache_compute_type
    with _model_cache_lock:
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

    lock_timeout_s = int(getattr(settings, "WHISPER_INIT_LOCK_TIMEOUT", 120) or 120)
    lock_key = f"whisper_init:{str(model_size).replace('/', '_')}:{device}:{compute_type}"
    deadline = time.time() + float(lock_timeout_s)
    have_lock = False
    try:
        try:
            from django.core.cache import cache
            while time.time() < deadline and not have_lock:
                try:
                    have_lock = bool(cache.add(lock_key, 1, timeout=lock_timeout_s))
                except Exception:
                    have_lock = True
                if not have_lock:
                    time.sleep(0.25)
        except Exception:
            have_lock = True

        retries = int(getattr(settings, "WHISPER_MODEL_LOAD_RETRIES", 2) or 2)
        backoff = float(getattr(settings, "WHISPER_MODEL_LOAD_BACKOFF", 1.0) or 1.0)
        attempt = 0
        last_error = None

        while attempt <= retries:
            try:
                model_obj = WhisperModel(
                    model_source,
                    device=device,
                    compute_type=compute_type,
                )
                with _model_cache_lock:
                    _model_cache = model_obj
                    _model_cache_device = device
                    _model_cache_compute_type = compute_type
                return model_obj
            except Exception as e:
                last_error = e
                attempt += 1
                if attempt > retries:
                    break
                time.sleep(backoff * float(attempt))

        raise RuntimeError(f"Falha interna Faster-Whisper: {last_error}")
    finally:
        if have_lock:
            try:
                from django.core.cache import cache
                cache.delete(lock_key)
            except Exception:
                pass


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