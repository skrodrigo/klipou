import logging

from django.conf import settings
from django.core.cache import cache
from google import genai

logger = logging.getLogger(__name__)

_gemini_client = None


def normalize_score_0_100(raw_score) -> float:
    try:
        s = float(raw_score or 0)
    except Exception:
        s = 0.0
    s = s * 10.0 if s <= 10.0 else s
    return float(max(0.0, min(s, 100.0)))


def get_duration_bounds_from_job(video_id: str) -> tuple[int, int]:
    """Return (min_duration, max_duration) using Job.configuration as source of truth.

    Accepts duration_min/max and legacy aliases.
    """
    try:
        from ..models import Job

        job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
        cfg = (job.configuration if job else None) or {}

        max_d = (
            cfg.get("duration_max")
            or cfg.get("max_clip_duration")
            or cfg.get("maxDuration")
            or cfg.get("max_clip_duration_seconds")
        )
        if max_d is None:
            max_d = 60
        max_d = int(max(10, min(int(max_d), 180)))

        min_d = (
            cfg.get("duration_min")
            or cfg.get("min_clip_duration")
            or cfg.get("minDuration")
            or cfg.get("min_clip_duration_seconds")
        )
        if min_d is None:
            min_d = max(10, int(round(max_d * 0.6)))

        min_d = int(max(5, min(int(min_d), max_d)))
        return min_d, max_d
    except Exception:
        return 10, 60


def get_gemini_client():
    global _gemini_client
    if _gemini_client:
        return _gemini_client

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def enforce_gemini_rate_limit(organization_id: str, kind: str) -> None:
    """Best-effort sliding window limiter via Django cache.

    If cache is unavailable, limiter is skipped.
    """
    org_key = (organization_id or "unknown").strip()
    k = (kind or "generic").strip().lower()

    window_seconds = int(getattr(settings, "GEMINI_RATE_LIMIT_WINDOW_SECONDS", 60) or 60)
    max_calls = int(getattr(settings, "GEMINI_RATE_LIMIT_MAX_CALLS", 60) or 60)

    cache_key = f"gemini_rl:{k}:{org_key}"
    try:
        cache.add(cache_key, 0, timeout=window_seconds)
        current = cache.incr(cache_key)
    except Exception:
        return

    if int(current) > int(max_calls):
        raise RuntimeError(f"Rate limit Gemini excedido (org={org_key} kind={k}).")


def log_gemini_usage(response, organization_id: str, kind: str, model: str) -> None:
    try:
        usage = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
        if usage is None:
            return

        prompt_tokens = getattr(usage, "prompt_token_count", None) or getattr(usage, "promptTokenCount", None)
        output_tokens = getattr(usage, "candidates_token_count", None) or getattr(usage, "candidatesTokenCount", None)
        total_tokens = getattr(usage, "total_token_count", None) or getattr(usage, "totalTokenCount", None)

        logger.info(
            "[gemini_usage] org=%s kind=%s model=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
            organization_id,
            kind,
            model,
            prompt_tokens,
            output_tokens,
            total_tokens,
        )
    except Exception:
        return
