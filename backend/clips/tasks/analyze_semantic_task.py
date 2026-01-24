import json
import logging
import re
import hashlib
import math
import time
from typing import Any, Optional
from celery import shared_task
from django.conf import settings
from google.genai import types

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status, get_plan_tier
from ..services.gemini_utils import (
    get_gemini_client,
    enforce_gemini_rate_limit,
    log_gemini_usage,
    normalize_score_0_100,
    get_duration_bounds_from_job,
)

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = 3

DEFAULT_SNAP_TOLERANCE_S = 1.0
DEFAULT_OVERLAP_RATIO = 0.90
DEFAULT_CHUNK_SECONDS = 600
DEFAULT_CHUNK_THRESHOLD_SECONDS = 1800
DEFAULT_CHUNK_THRESHOLD_CHARS = 45000
DEFAULT_MAX_OUTPUT_TOKENS = 12288
DEFAULT_TEMPERATURE = 0.4
DEFAULT_MAX_CLIPS = 25
DEFAULT_MIN_CLIPS = 5


def _get_config(key: str, default: Any, type_cast=None) -> Any:
    """Helper seguro para pegar configurações"""
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


def _prompt_hash(prompt: str, *, model: str, schema: dict, temperature: float) -> str:
    """Hash do prompt incluindo temperatura para cache"""
    h = hashlib.sha256()
    h.update(str(ANALYSIS_VERSION).encode("utf-8"))
    h.update(b"\n")
    h.update((model or "").encode("utf-8"))
    h.update(b"\n")
    h.update(str(temperature).encode("utf-8"))
    h.update(b"\n")
    try:
        h.update(json.dumps(schema or {}, sort_keys=True).encode("utf-8"))
    except Exception:
        h.update(repr(schema).encode("utf-8", errors="ignore"))
    h.update(b"\n")
    h.update((prompt or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _safe_update_job_status(
    video_id: str,
    status: str,
    *,
    progress: Optional[int] = None,
    current_step: Optional[str] = None
):
    """Wrapper seguro para update_job_status"""
    try:
        update_job_status(video_id, status, progress=progress, current_step=current_step)
    except Exception as e:
        logger.warning(f"[analyze] update_job_status failed for {video_id}: {e}")


def _transcript_hash(transcript: Transcript) -> str:
    """Hash SHA-256 da transcrição para cache"""
    segments = transcript.segments or []
    full_text = transcript.full_text or ""

    h = hashlib.sha256()
    h.update(str(transcript.video_id).encode("utf-8"))
    h.update(b"\n")
    h.update(str(transcript.language or "").encode("utf-8"))
    h.update(b"\n")
    h.update(str(len(segments)).encode("utf-8"))
    h.update(b"\n")
    h.update(full_text.encode("utf-8", errors="ignore"))
    
    h.update(b"\nsalt_v3\n")
    
    return h.hexdigest()


def _should_skip_gemini_analysis(transcript: Transcript, cfg: dict) -> bool:
    """Verifica se pode usar análise em cache"""
    analysis_data = transcript.analysis_data or {}
    meta = analysis_data.get("meta") if isinstance(analysis_data, dict) else None
    if not isinstance(meta, dict):
        return False

    if meta.get("transcript_hash") != _transcript_hash(transcript):
        logger.debug("[analyze] cache miss: transcript changed")
        return False

    if meta.get("analysis_version") != ANALYSIS_VERSION:
        logger.debug("[analyze] cache miss: analysis version changed")
        return False

    if meta.get("prompt_hash") and cfg.get("prompt_hash"):
        if str(meta.get("prompt_hash")) != str(cfg.get("prompt_hash")):
            logger.debug("[analyze] cache miss: prompt changed")
            return False

    prev_cfg = meta.get("config")
    if not isinstance(prev_cfg, dict):
        logger.debug("[analyze] cache miss: no previous config")
        return False

    critical_keys = ("min_duration", "max_duration", "max_clips_desired")
    for k in critical_keys:
        prev_val = int(prev_cfg.get(k) or 0)
        curr_val = int(cfg.get(k) or 0)
        if prev_val != curr_val:
            logger.debug(f"[analyze] cache miss: {k} changed {prev_val} -> {curr_val}")
            return False

    candidates = analysis_data.get("candidates")
    has_valid = isinstance(candidates, list) and len(candidates) > 0
    
    if not has_valid:
        logger.debug("[analyze] cache miss: no valid candidates")
    
    return has_valid


def _format_transcript_with_timestamps(segments: list) -> str:
    """Formata transcrição com timestamps [start-end]"""
    if not segments:
        return ""

    buffer = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
            
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = (seg.get("text") or "").strip()
        
        if not text:
            continue
            
        try:
            buffer.append(f"[{float(start):.1f}-{float(end):.1f}] {text}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp in segment: start={start} end={end}")
            continue

    return "\n".join(buffer)


def _clean_number(num) -> int | float:
    """Converte número removendo .0 desnecessário"""
    try:
        f_num = float(num)
        if math.isnan(f_num) or math.isinf(f_num):
            return 0
        if f_num.is_integer():
            return int(f_num)
        return round(f_num, 2) 
    except (ValueError, TypeError):
        return 0


def _to_float(x, default: Optional[float] = None) -> Optional[float]:
    """Conversão segura para float com validação"""
    try:
        if x is None:
            return default
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _snap_time_to_segments(t: float, segments: list[dict], tolerance_s: float) -> float:
    """Ajusta timestamp para boundary mais próximo nos segments"""
    if not segments:
        return t

    best_time = None
    best_delta = None

    for seg in segments:
        if not isinstance(seg, dict):
            continue
            
        start = _to_float(seg.get("start"), None)
        end = _to_float(seg.get("end"), None)
        
        for candidate_time in (start, end):
            if candidate_time is None:
                continue
                
            delta = abs(candidate_time - t)
            
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_time = candidate_time

    if best_time is None or best_delta is None:
        return t
        
    if best_delta <= float(tolerance_s):
        return float(best_time)
        
    return t


def _is_close_to_any_segment_boundary(
    t: float,
    segments: list[dict],
    tolerance_s: float
) -> bool:
    """Verifica se timestamp está próximo de algum boundary"""
    if not segments:
        return False
        
    tt = _to_float(t, None)
    if tt is None:
        return False
        
    tolerance = float(tolerance_s)
    
    for seg in segments:
        if not isinstance(seg, dict):
            continue
            
        for key in ("start", "end"):
            seg_time = _to_float(seg.get(key), None)
            if seg_time is None:
                continue
                
            if abs(float(seg_time) - float(tt)) <= tolerance:
                return True
                
    return False


def _validate_and_normalize_candidates(
    candidates: list,
    *,
    segments: list[dict],
    video_duration_s: float,
    min_duration: int,
    max_duration: int,
    snap_to_segments: bool,
    snap_tolerance_s: float,
    require_segment_bounds: bool,
) -> tuple[list[dict], dict]:
    """
    Valida e normaliza candidatos retornados pelo Gemini
    
    Returns:
        (candidatos_válidos, estatísticas)
    """
    kept: list[dict] = []
    stats = {
        "input": len(candidates) if isinstance(candidates, list) else 0,
        "kept": 0,
        "dropped_non_dict": 0,
        "dropped_invalid_numbers": 0,
        "dropped_outside_video": 0,
        "dropped_duration_bounds": 0,
        "dropped_missing_segment_bounds": 0,
        "snapped": 0,
    }

    if not isinstance(candidates, list):
        return [], stats

    video_dur = float(video_duration_s or 0.0)
    if video_dur <= 0:
        video_dur = 0.0

    epsilon = float(_get_config("GEMINI_ANALYZE_DURATION_EPSILON_S", 0.25, float))
    
    for c in candidates:
        if not isinstance(c, dict):
            stats["dropped_non_dict"] += 1
            continue

        start_time = _to_float(c.get("start_time"), None)
        end_time = _to_float(c.get("end_time"), None)
        score_raw = _to_float(c.get("engagement_score"), 0.0)
        
        if start_time is None or end_time is None:
            stats["dropped_invalid_numbers"] += 1
            continue

        start_time = float(max(0.0, start_time))
        end_time = float(max(0.0, end_time))
        
        if video_dur > 0:
            start_time = float(min(start_time, video_dur))
            end_time = float(min(end_time, video_dur))

        snapped_ok = True
        if (snap_to_segments or require_segment_bounds) and segments:
            original_times = (start_time, end_time)
            
            start_time = _snap_time_to_segments(start_time, segments, snap_tolerance_s)
            end_time = _snap_time_to_segments(end_time, segments, snap_tolerance_s)
            
            if original_times != (start_time, end_time):
                stats["snapped"] += 1

            if require_segment_bounds:
                start_ok = _is_close_to_any_segment_boundary(start_time, segments, snap_tolerance_s)
                end_ok = _is_close_to_any_segment_boundary(end_time, segments, snap_tolerance_s)
                snapped_ok = bool(start_ok and end_ok)

        if require_segment_bounds and segments and not snapped_ok:
            stats["dropped_missing_segment_bounds"] += 1
            continue

        if end_time <= start_time:
            stats["dropped_invalid_numbers"] += 1
            continue

        if video_dur > 0 and (start_time < 0 or end_time > video_dur + epsilon):
            stats["dropped_outside_video"] += 1
            continue

        duration = float(end_time - start_time)
        min_dur = float(min_duration)
        max_dur = float(max_duration)
        
        if duration < min_dur - epsilon or duration > max_dur + epsilon:
            stats["dropped_duration_bounds"] += 1
            continue

        score_0_100 = float(normalize_score_0_100(score_raw))
        
        sanitized = {
            "text": str(c.get("text", ""))[:5000],
            "start_time": _clean_number(start_time),
            "end_time": _clean_number(end_time),
            "engagement_score": _clean_number(score_0_100),
            "hook_title": str(c.get("hook_title", ""))[:200],
            "tone": str(c.get("tone", ""))[:100],
            "category": str(c.get("category", "GOOD")).upper()[:20],
        }
        
        kept.append(sanitized)

    stats["kept"] = len(kept)
    return kept, stats


def _chunk_segments_by_time(segments: list, chunk_seconds: int) -> list[list[dict]]:
    """Divide segments em chunks temporais"""
    if not segments or not chunk_seconds or chunk_seconds <= 0:
        return []

    chunks: list[list[dict]] = []
    current: list[dict] = []
    chunk_start: Optional[float] = None

    for seg in segments:
        if not isinstance(seg, dict):
            continue

        start_f = _to_float(seg.get("start"), None)
        end_f = _to_float(seg.get("end"), None)

        if start_f is None:
            return [segments] if segments else []

        if chunk_start is None:
            chunk_start = start_f

        boundary = end_f if end_f is not None else start_f
        
        if boundary - chunk_start > float(chunk_seconds) and current:
            chunks.append(current)
            current = []
            chunk_start = start_f

        current.append(seg)

    if current:
        chunks.append(current)

    return chunks


def _merge_dedup_candidates_by_overlap(
    candidates: list[dict],
    *,
    overlap_ratio: float,
    keep: int,
) -> tuple[list[dict], dict]:

    stats = {
        "input": len(candidates or []),
        "kept": 0,
        "dropped_overlap": 0
    }
    
    if not candidates:
        return [], stats

    def get_times(c: dict) -> tuple[float, float]:
        """Extrai timestamps de forma segura"""
        return (
            float(c.get("start_time", 0) or 0),
            float(c.get("end_time", 0) or 0)
        )

    def get_score(c: dict) -> float:
        """Extrai score de forma segura"""
        try:
            return float(c.get("engagement_score", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    def calculate_overlap(a: dict, b: dict) -> float:
        """Calcula ratio de overlap entre dois candidatos"""
        a_start, a_end = get_times(a)
        b_start, b_end = get_times(b)
        
        inter_start = max(a_start, b_start)
        inter_end = min(a_end, b_end)
        
        if inter_end <= inter_start:
            return 0.0
            
        intersection = inter_end - inter_start
        dur_a = max(0.001, a_end - a_start)
        dur_b = max(0.001, b_end - b_start)
        
        return float(intersection / min(dur_a, dur_b))

    ordered = sorted(
        candidates,
        key=lambda c: (get_score(c), -get_times(c)[0]),
        reverse=True
    )

    kept: list[dict] = []
    
    for candidate in ordered:
        if len(kept) >= int(keep):
            break
            
        is_duplicate = False
        for kept_candidate in kept:
            if calculate_overlap(candidate, kept_candidate) >= float(overlap_ratio):
                is_duplicate = True
                stats["dropped_overlap"] += 1
                break
                
        if not is_duplicate:
            kept.append(candidate)

    stats["kept"] = len(kept)
    return kept, stats


@shared_task(bind=True, max_retries=3)
def analyze_semantic_task(self, video_id: str) -> dict:

    video = None
    
    try:
        logger.info(f"[analyze] Iniciando para video_id={video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)

        video.status = "analyzing"
        video.current_step = "analyzing"
        video.save()
        _safe_update_job_status(
            str(video.video_id),
            "analyzing",
            progress=45,
            current_step="analyzing"
        )

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise ValueError("Transcrição não encontrada")

        segments = transcript.segments or []
        if not segments:
            raise ValueError("Transcrição sem segments")
            
        language = transcript.language or "en"

        min_d, max_d = get_duration_bounds_from_job(video_id=str(video.video_id))
        
        max_clips_desired = _get_config("MAX_CLIPS_DESIRED", DEFAULT_MAX_CLIPS, int)
        
        try:
            from ..models import Job
            job = Job.objects.filter(
                video_id=str(video.video_id)
            ).order_by("-created_at").first()
            
            if job and job.configuration:
                cfg = job.configuration
                max_clips_desired = int(
                    cfg.get("max_clips_desired") or
                    cfg.get("maxClips") or
                    max_clips_desired
                )
        except Exception as e:
            logger.warning(f"[analyze] Failed to load job config: {e}")

        max_clips_desired = int(max(
            _get_config("MIN_CLIPS_DESIRED", DEFAULT_MIN_CLIPS, int),
            min(max_clips_desired, DEFAULT_MAX_CLIPS)
        ))

        response_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "start_time": {"type": "number"},
                            "end_time": {"type": "number"},
                            "engagement_score": {"type": "number"},
                            "hook_title": {"type": "string"},
                            "tone": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": ["MUST_HAVE", "GOOD", "FILLER"],
                            },
                        },
                        "required": [
                            "text",
                            "start_time",
                            "end_time",
                            "engagement_score",
                            "hook_title",
                            "tone",
                            "category"
                        ],
                    },
                },
                "overall_tone": {"type": "string"},
                "key_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["title", "description", "candidates", "overall_tone", "key_topics"],
        }

        model_name = "gemini-2.5-flash-lite"
        temperature = _get_config("GEMINI_ANALYZE_TEMPERATURE", DEFAULT_TEMPERATURE, float)
        max_candidates = int(max(5, min(max_clips_desired, 25)))
        
        if language.startswith("pt"):
            base_instructions = (
                "Você é um editor de vídeo e estrategista de conteúdo para Shorts/Reels/TikTok.\n\n"
                "TAREFA:\n"
                "- Dada a transcrição com timestamps no formato [início-fim], escolha os melhores trechos para virar clips.\n\n"
                "REGRAS (obrigatórias):\n"
                "1) Use apenas timestamps que existem no texto fornecido. Não invente tempos.\n"
                f"2) Cada clip deve ter duração entre {int(min_d)} e {int(max_d)} segundos.\n"
                "3) Selecione trechos autossuficientes (que fazem sentido sem contexto anterior).\n"
                f"4) Retorne no máximo {int(max_candidates)} candidatos.\n"
                "5) engagement_score deve estar na escala 0-10 (pode ter decimais, ex: 7.5).\n"
                "6) Ordene candidatos por qualidade (melhor primeiro).\n\n"
                "SAÍDA:\n"
                "- Retorne APENAS JSON válido conforme o schema (sem markdown, sem texto extra)."
            )
        else:
            base_instructions = (
                "You are a world-class video editor and viral content strategist.\n\n"
                "TASK:\n"
                "- Given a transcript with timestamps in [start-end] format, select the best segments to become short clips.\n\n"
                "RULES (mandatory):\n"
                "1) Use only timestamps that exist in the provided text. Do not invent times.\n"
                f"2) Each clip duration must be between {int(min_d)} and {int(max_d)} seconds.\n"
                "3) Select stand-alone segments (understandable without prior context).\n"
                f"4) Return at most {int(max_candidates)} candidates.\n"
                "5) engagement_score must be on a 0-10 scale (decimals allowed, e.g. 7.5).\n"
                "6) Sort candidates by quality (best first).\n\n"
                "OUTPUT:\n"
                "- Return ONLY valid JSON matching the schema (no markdown, no extra text)."
            )

        prompt_hash = _prompt_hash(
            base_instructions,
            model=model_name,
            schema=response_schema,
            temperature=temperature
        )

        analyze_cfg = {
            "min_duration": int(min_d),
            "max_duration": int(max_d),
            "max_clips_desired": int(max_clips_desired),
            "prompt_hash": prompt_hash,
        }

        if _should_skip_gemini_analysis(transcript, analyze_cfg):
            logger.info(f"[analyze] Using cached analysis for video_id={video_id}")
            analysis_result = transcript.analysis_data or {}
            
            for c in analysis_result.get("candidates") or []:
                if isinstance(c, dict):
                    raw_score = c.get("engagement_score", 0)
                    c["engagement_score"] = _clean_number(normalize_score_0_100(raw_score))
        else:
            logger.info(f"[analyze] Running Gemini analysis for video_id={video_id}")
            analysis_result = _analyze_transcript_with_gemini(
                segments=segments,
                language=language,
                min_duration=min_d,
                max_duration=max_d,
                video_duration_s=float(video.duration or 0) if video.duration else 0.0,
                video_id=str(video.video_id),
                organization_id=str(org.organization_id),
                max_clips_desired=max_clips_desired,
                temperature=temperature,
            )

        existing_meta = analysis_result.get("meta")
        if not isinstance(existing_meta, dict):
            existing_meta = {}

        analysis_result["meta"] = {
            **existing_meta,
            "analysis_version": ANALYSIS_VERSION,
            "transcript_hash": _transcript_hash(transcript),
            "config": analyze_cfg,
        }

        if "candidates" in analysis_result:
            raw_candidates = analysis_result.get("candidates") or []

            snap_to_segments = _get_config("GEMINI_ANALYZE_SNAP_TO_SEGMENTS", True, bool)
            snap_tolerance = _get_config("GEMINI_ANALYZE_SNAP_TOLERANCE_S", DEFAULT_SNAP_TOLERANCE_S, float)
            require_bounds = _get_config("GEMINI_ANALYZE_REQUIRE_SEGMENT_BOUNDS", True, bool)

            normalized, validation_stats = _validate_and_normalize_candidates(
                raw_candidates,
                segments=segments,
                video_duration_s=float(video.duration or 0) if video.duration else 0.0,
                min_duration=int(min_d),
                max_duration=int(max_d),
                snap_to_segments=snap_to_segments,
                snap_tolerance_s=float(snap_tolerance),
                require_segment_bounds=require_bounds,
            )

            if not normalized:
                fallback_max = int(
                    _get_config("FALLBACK_MAX_CANDIDATES", DEFAULT_MAX_CLIPS, int)
                )
                normalized = _fallback_candidates_from_segments(
                    segments,
                    min_duration=float(min_d),
                    max_duration=float(max_d),
                    max_candidates=fallback_max,
                )
                validation_stats["fallback_generated"] = len(normalized)

            analysis_result["candidates"] = normalized
            
            logger.info(
                "[analyze] Validation: input=%s kept=%s "
                "dropped_non_dict=%s dropped_invalid_numbers=%s "
                "dropped_outside_video=%s dropped_duration_bounds=%s "
                "dropped_missing_segment_bounds=%s snapped=%s",
                validation_stats.get("input"),
                validation_stats.get("kept"),
                validation_stats.get("dropped_non_dict"),
                validation_stats.get("dropped_invalid_numbers"),
                validation_stats.get("dropped_outside_video"),
                validation_stats.get("dropped_duration_bounds"),
                validation_stats.get("dropped_missing_segment_bounds"),
                validation_stats.get("snapped"),
            )

        if "candidates" in analysis_result:
            for c in analysis_result["candidates"]:
                c["start_time"] = _clean_number(c.get("start_time", 0))
                c["end_time"] = _clean_number(c.get("end_time", 0))
                c["engagement_score"] = _clean_number(c.get("engagement_score", 0))

        transcript.analysis_data = analysis_result
        transcript.save()

        logger.info(
            f"[analyze] Completed for video_id={video_id}: "
            f"{len(analysis_result.get('candidates', []))} candidates"
        )

        video.last_successful_step = "analyzing"
        video.status = "embedding"
        video.current_step = "embedding"
        video.save()

        _safe_update_job_status(
            str(video.video_id),
            "embedding",
            progress=50,
            current_step="embedding"
        )

        from .embed_classify_task import embed_classify_task
        embed_classify_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.classify.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "candidates_found": len(analysis_result.get("candidates", [])),
            "status": "success",
        }

    except Video.DoesNotExist:
        logger.error(f"[analyze] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[analyze] Error for video_id={video_id}: {e}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.retry_count += 1
            video.save()

            _safe_update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="analyzing"
            )

            msg = str(e).lower()
            
            permanent_errors = (
                "gemini_api_key" in msg or
                "api key" in msg or
                "unauthorized" in msg or
                "permission" in msg or
                "not configured" in msg or
                "não configur" in msg or
                "invalid" in msg
            )
            
            json_errors = (
                "could not extract valid json" in msg or
                "empty response text" in msg or
                "response text is not a string" in msg
            )
            
            rate_limited = (
                "rate limit" in msg or
                "429" in msg or
                ("excedido" in msg and "rate" in msg) or
                "quota" in msg
            )
            
            base_countdown = 2 ** self.request.retries
            
            if rate_limited:
                countdown = int(max(base_countdown, 60))  # Mínimo 1 minuto
                logger.warning(f"[analyze] Rate limited, retrying in {countdown}s")
            elif json_errors and self.request.retries >= 1:
                logger.error(f"[analyze] JSON error after retry, giving up")
                return {"error": str(e), "status": "failed"}
            else:
                countdown = base_countdown
            
            if not permanent_errors and self.request.retries < self.max_retries:
                logger.info(
                    f"[analyze] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                    f"in {countdown}s"
                )
                raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e), "status": "failed"}


def _analyze_transcript_with_gemini(
    segments: list,
    language: str,
    min_duration: int,
    max_duration: int,
    video_duration_s: float,
    video_id: str,
    organization_id: str,
    max_clips_desired: int,
    temperature: float,
) -> dict:

    enable_chunking = _get_config("GEMINI_ANALYZE_ENABLE_CHUNKING", True, bool)
    chunk_seconds = _get_config("GEMINI_ANALYZE_CHUNK_SECONDS", DEFAULT_CHUNK_SECONDS, int)
    chunk_threshold_s = _get_config("GEMINI_ANALYZE_CHUNK_THRESHOLD_SECONDS", DEFAULT_CHUNK_THRESHOLD_SECONDS, int)
    chunk_threshold_chars = _get_config("GEMINI_ANALYZE_CHUNK_THRESHOLD_CHARS", DEFAULT_CHUNK_THRESHOLD_CHARS, int)

    formatted_text = _format_transcript_with_timestamps(segments)

    should_chunk = False
    if enable_chunking and chunk_seconds > 0:
        video_dur = video_duration_s if isinstance(video_duration_s, (int, float)) else 0
        
        if video_dur >= chunk_threshold_s:
            should_chunk = True
            logger.info(f"[analyze] Chunking by duration: {video_dur}s >= {chunk_threshold_s}s")
        elif len(formatted_text) >= chunk_threshold_chars:
            should_chunk = True
            logger.info(f"[analyze] Chunking by chars: {len(formatted_text)} >= {chunk_threshold_chars}")

    if not should_chunk:
        logger.info("[analyze] Single-pass analysis (no chunking)")
        return _analyze_with_gemini(
            formatted_text,
            language,
            min_duration=min_duration,
            max_duration=max_duration,
            organization_id=organization_id,
            max_candidates=max_clips_desired,
            temperature=temperature,
        )

    chunks = _chunk_segments_by_time(segments, chunk_seconds)
    
    if not chunks:
        logger.warning("[analyze] Chunking failed, falling back to single-pass")
        return _analyze_with_gemini(
            formatted_text,
            language,
            min_duration=min_duration,
            max_duration=max_duration,
            organization_id=organization_id,
            max_candidates=max_clips_desired,
            temperature=temperature,
        )

    logger.info(f"[analyze] Processing {len(chunks)} chunks")

    merged_candidates: list[dict] = []
    merged_title: Optional[str] = None
    merged_description: Optional[str] = None
    merged_overall_tone: Optional[str] = None
    merged_key_topics: list[str] = []
    fillers_dropped = 0
    chunks_failed = 0

    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks):
        _safe_update_job_status(
            video_id,
            "analyzing",
            progress=45 + int((i / max(1, total_chunks)) * 4),
            current_step=f"analyzing_chunk_{i+1}/{total_chunks}",
        )

        chunk_text = _format_transcript_with_timestamps(chunk)
        if not chunk_text.strip():
            logger.warning(f"[analyze] Chunk {i+1}/{total_chunks} is empty, skipping")
            continue

        start_time = time.time()
        
        try:
            chunk_result = _analyze_with_gemini(
                chunk_text,
                language,
                min_duration=min_duration,
                max_duration=max_duration,
                organization_id=organization_id,
                max_candidates=max(10, min(20, max_clips_desired)),
                temperature=temperature,
            )
            
            elapsed = time.time() - start_time
            logger.info(
                f"[analyze] Chunk {i+1}/{total_chunks} done: "
                f"chars={len(chunk_text)} elapsed={elapsed:.2f}s"
            )
            
        except Exception as e:
            chunks_failed += 1
            elapsed = time.time() - start_time
            logger.warning(
                f"[analyze] Chunk {i+1}/{total_chunks} failed after {elapsed:.2f}s: {e}"
            )
            continue

        if not merged_title:
            title = (chunk_result or {}).get("title")
            if isinstance(title, str) and title.strip():
                merged_title = title.strip()
                
        if not merged_description:
            desc = (chunk_result or {}).get("description")
            if isinstance(desc, str) and desc.strip():
                merged_description = desc.strip()
                
        if not merged_overall_tone:
            tone = (chunk_result or {}).get("overall_tone")
            if isinstance(tone, str) and tone.strip():
                merged_overall_tone = tone.strip()

        topics = (chunk_result or {}).get("key_topics") or []
        if isinstance(topics, list):
            topics_lower = [t.strip().lower() for t in merged_key_topics if isinstance(t, str)]
            for topic in topics:
                if isinstance(topic, str) and topic.strip():
                    topic_clean = topic.strip()
                    if topic_clean.lower() not in topics_lower:
                        merged_key_topics.append(topic_clean)
                        topics_lower.append(topic_clean.lower())

        candidates = (chunk_result or {}).get("candidates") or []
        if isinstance(candidates, list):
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                    
                category = (c.get("category") or "").strip().upper()
                if category == "FILLER":
                    fillers_dropped += 1
                    continue
                    
                merged_candidates.append(c)

    if not merged_candidates:
        error_msg = (
            f"Nenhum candidato válido após processar {total_chunks} chunks "
            f"({chunks_failed} failed, {fillers_dropped} fillers dropped)"
        )
        logger.error(f"[analyze] {error_msg}")
        raise RuntimeError(error_msg)

    logger.info(
        f"[analyze] Merged {len(merged_candidates)} candidates from {total_chunks} chunks "
        f"({chunks_failed} failed, {fillers_dropped} fillers dropped)"
    )

    for c in merged_candidates:
        if isinstance(c, dict):
            raw_score = c.get("engagement_score", 0)
            c["engagement_score"] = _clean_number(normalize_score_0_100(raw_score))

    overlap_ratio = _get_config("GEMINI_ANALYZE_DEDUP_OVERLAP_RATIO", DEFAULT_OVERLAP_RATIO, float)
    
    merged_candidates, dedup_stats = _merge_dedup_candidates_by_overlap(
        merged_candidates,
        overlap_ratio=overlap_ratio,
        keep=int(max_clips_desired),
    )
    
    logger.info(
        f"[analyze] Dedup: input={dedup_stats.get('input')} "
        f"kept={dedup_stats.get('kept')} "
        f"dropped_overlap={dedup_stats.get('dropped_overlap')} "
        f"overlap_ratio={overlap_ratio}"
    )

    try:
        merged_candidates.sort(
            key=lambda c: float(c.get("engagement_score", 0) or 0),
            reverse=True
        )
    except Exception as e:
        logger.warning(f"[analyze] Failed to sort candidates: {e}")

    merged_candidates = merged_candidates[:int(max_clips_desired)]

    result = {
        "title": merged_title or "",
        "description": merged_description or "",
        "candidates": merged_candidates,
        "overall_tone": merged_overall_tone or "",
        "key_topics": merged_key_topics,
        "meta": {
            "chunks_total": total_chunks,
            "chunks_failed": chunks_failed,
            "fillers_dropped": fillers_dropped,
            "dedup": dedup_stats,
        },
    }

    return result


def _analyze_with_gemini(
    formatted_text: str,
    language: str,
    min_duration: int,
    max_duration: int,
    organization_id: str,
    max_candidates: int,
    temperature: float,
) -> dict:

    client = get_gemini_client()

    enforce_gemini_rate_limit(organization_id=organization_id, kind="analyze")

    response_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "start_time": {"type": "number"},
                        "end_time": {"type": "number"},
                        "engagement_score": {"type": "number"},
                        "hook_title": {"type": "string"},
                        "tone": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["MUST_HAVE", "GOOD", "FILLER"],
                        },
                    },
                    "required": [
                        "text",
                        "start_time",
                        "end_time",
                        "engagement_score",
                        "hook_title",
                        "tone",
                        "category"
                    ],
                },
            },
            "overall_tone": {"type": "string"},
            "key_topics": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["title", "description", "candidates", "overall_tone", "key_topics"],
    }

    max_candidates = int(max(5, min(max_candidates, 25)))

    if language.startswith("pt"):
        base_instructions = (
            "Você é um editor de vídeo e estrategista de conteúdo para Shorts/Reels/TikTok.\n\n"
            "TAREFA:\n"
            "- Dada a transcrição com timestamps no formato [início-fim], escolha os melhores trechos para virar clips.\n\n"
            "REGRAS (obrigatórias):\n"
            "1) Use apenas timestamps que existem no texto fornecido. Não invente tempos.\n"
            f"2) Cada clip deve ter duração entre {min_duration} e {max_duration} segundos.\n"
            "3) Selecione trechos autossuficientes (que fazem sentido sem contexto anterior).\n"
            f"4) Retorne no máximo {max_candidates} candidatos.\n"
            "5) engagement_score deve estar na escala 0-10 (pode ter decimais, ex: 7.5).\n"
            "6) Ordene candidatos por qualidade (melhor primeiro).\n\n"
            "SAÍDA:\n"
            "- Retorne APENAS JSON válido conforme o schema (sem markdown, sem texto extra)."
        )
        prompt = (
            f"{base_instructions}\n\n"
            "Idioma do Vídeo: Português.\n\n"
            "Retorne um JSON com title, description, candidates, overall_tone e key_topics.\n\n"
            f"Transcrição Formatada:\n{formatted_text}"
        )
    else:
        base_instructions = (
            "You are a world-class video editor and viral content strategist.\n\n"
            "TASK:\n"
            "- Given a transcript with timestamps in [start-end] format, select the best segments to become short clips.\n\n"
            "RULES (mandatory):\n"
            "1) Use only timestamps that exist in the provided text. Do not invent times.\n"
            f"2) Each clip duration must be between {min_duration} and {max_duration} seconds.\n"
            "3) Select stand-alone segments (understandable without prior context).\n"
            f"4) Return at most {max_candidates} candidates.\n"
            "5) engagement_score must be on a 0-10 scale (decimals allowed, e.g. 7.5).\n"
            "6) Sort candidates by quality (best first).\n\n"
            "OUTPUT:\n"
            "- Return ONLY valid JSON matching the schema (no markdown, no extra text)."
        )
        prompt = (
            f"{base_instructions}\n\n"
            "Return a JSON with title, description, candidates, overall_tone and key_topics.\n\n"
            f"Formatted Transcript:\n{formatted_text}"
        )

    model_name = "gemini-2.5-flash-lite"
    max_output_tokens = _get_config("GEMINI_ANALYZE_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS, int)

    try:
        response = client.models.generate_content(
            model=f'models/{model_name}',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=float(temperature),
                max_output_tokens=int(max_output_tokens),
            ),
        )
    except Exception as e:
        logger.error(f"[analyze] Gemini API call failed: {e}")
        raise

    log_gemini_usage(response, organization_id=organization_id, kind="analyze", model=model_name)

    raw_text = _get_gemini_response_text(response)
    logger.debug(f"[analyze] Gemini response: {len(raw_text) if isinstance(raw_text, str) else 0} chars")

    try:
        analysis_data = _safe_load_json_response(raw_text)
    except json.JSONDecodeError as e:
        logger.warning(f"[analyze] Invalid JSON, attempting repair: {e}")
        
        try:
            analysis_data = _repair_gemini_json(client, raw_text, response_schema)
            logger.info("[analyze] JSON repair successful")
        except json.JSONDecodeError as e2:
            logger.error(f"[analyze] JSON repair failed: {e2}")
            logger.error(f"[analyze] Raw response preview: {raw_text[:500]}")
            raise

    meta = analysis_data.get("meta") if isinstance(analysis_data, dict) else None
    if not isinstance(meta, dict):
        meta = {}

    prompt_hash = _prompt_hash(prompt, model=model_name, schema=response_schema, temperature=temperature)
    
    meta.update({
        "model": model_name,
        "prompt_hash": prompt_hash,
        "temperature": float(temperature),
    })
    
    analysis_data["meta"] = meta

    if "candidates" in analysis_data:
        candidates = analysis_data.get("candidates") or []
        
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict):
                    raw_score = c.get("engagement_score", 0)
                    c["engagement_score"] = _clean_number(normalize_score_0_100(raw_score))
            
            analysis_data["candidates"] = candidates[:max_candidates]

    candidates_count = len((analysis_data or {}).get("candidates", []))
    logger.info(f"[analyze] Gemini returned {candidates_count} candidates")
    
    return analysis_data


def _safe_load_json_response(text: str) -> dict:

    if not isinstance(text, str):
        raise json.JSONDecodeError("Response text is not a string", str(text), 0)

    raw = text.replace("\ufeff", "").replace("\x00", "").strip()
    
    if not raw:
        raise json.JSONDecodeError("Empty response text", raw, 0)

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("JSON root is not an object", raw[:5000], 0)
        return parsed
    except json.JSONDecodeError:
        pass

    fenced = _extract_json_from_fences(raw)
    if fenced is not None:
        try:
            parsed = json.loads(fenced)
            if not isinstance(parsed, dict):
                raise json.JSONDecodeError("JSON root is not an object", fenced[:5000], 0)
            return parsed
        except json.JSONDecodeError:
            pass

    extracted = _extract_first_json_value(raw)
    if extracted is not None:
        parsed = json.loads(extracted)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("JSON root is not an object", extracted[:5000], 0)
        return parsed

    if "{" in raw and "}" in raw:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if 0 <= start < end:
                candidate = raw[start: end + 1].strip()
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    preview = raw[:5000]
    raise json.JSONDecodeError("Could not extract valid JSON from response", preview, 0)


def _get_gemini_response_text(response) -> str:
    """Extrai texto da resposta Gemini"""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None) or []
    parts: list[str] = []
    
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
            
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                parts.append(part_text)

    return "\n".join(parts).strip()


def _repair_gemini_json(client, raw_text: str, response_schema: dict) -> dict:
    
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise json.JSONDecodeError("Empty response text", str(raw_text), 0)

    logger.info("[analyze] Attempting JSON repair with Gemini")

    repair_prompt = (
        "Converta o conteúdo abaixo em JSON VÁLIDO que siga exatamente o schema. "
        "Retorne APENAS o JSON (sem markdown, sem texto extra, sem explicações).\n\n"
        "CONTEÚDO:\n"
        f"{raw_text[:10000]}"  # Limita tamanho para evitar custos excessivos
    )

    try:
        repair_response = client.models.generate_content(
            model='models/gemini-2.5-flash-lite',
            contents=repair_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.0,
                max_output_tokens=_get_config("GEMINI_ANALYZE_REPAIR_MAX_OUTPUT_TOKENS", 8192, int),
            ),
        )
    except Exception as e:
        logger.error(f"[analyze] JSON repair API call failed: {e}")
        raise json.JSONDecodeError("Repair API call failed", str(raw_text), 0)

    repaired_text = _get_gemini_response_text(repair_response)
    
    return _safe_load_json_response(repaired_text)


def _extract_json_from_fences(text: str) -> Optional[str]:
    """Extrai JSON de dentro de code fences markdown"""
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    
    if not match:
        return None
        
    fenced = match.group(1).strip()
    
    extracted = _extract_first_json_value(fenced)
    
    return extracted.strip() if extracted is not None else fenced


def _extract_first_json_value(text: str) -> Optional[str]:

    obj_start = text.find("{")
    arr_start = text.find("[")

    if obj_start == -1 and arr_start == -1:
        return None

    if obj_start == -1:
        start = arr_start
        open_char = "["
        close_char = "]"
    elif arr_start == -1:
        start = obj_start
        open_char = "{"
        close_char = "}"
    else:
        start = min(obj_start, arr_start)
        if start == obj_start:
            open_char = "{"
            close_char = "}"
        else:
            open_char = "["
            close_char = "]"

    in_string = False
    escape = False
    depth = 0
    
    for i in range(start, len(text)):
        char = text[i]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start: i + 1].strip()

    return None