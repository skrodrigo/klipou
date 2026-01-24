import logging
from celery import shared_task
import os

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status
from ..services.gemini_utils import get_duration_bounds_from_job

logger = logging.getLogger(__name__)

_DURATION_PREFILTER_SLACK = float(os.getenv("CLIP_DURATION_PREFILTER_SLACK", "1.10") or 1.10)
_DEFAULT_OVERLAP_RATIO = float(os.getenv("CLIP_OVERLAP_RATIO_DEFAULT", "0.75") or 0.75)
_RELAXED_OVERLAP_RATIO = float(os.getenv("CLIP_OVERLAP_RATIO_RELAXED", "0.92") or 0.92)
_TARGET_ESTIMATE_FACTOR = float(os.getenv("CLIP_TARGET_ESTIMATE_FACTOR", "1.8") or 1.8)

_DEFAULT_RELAX_SCORE_STEPS = (60.0, 50.0, 40.0, 30.0)
_DEFAULT_FALLBACK_MIN_GAP = float(os.getenv("CLIP_FALLBACK_MIN_GAP_SECONDS", "3.0") or 3.0)
_DEFAULT_CANDIDATE_TS_TOLERANCE = float(os.getenv("CLIP_CANDIDATE_TS_TOLERANCE", "0.5") or 0.5)

_DEFAULT_SCORE_SCALE_MODE = str(os.getenv("CLIP_SCORE_SCALE_MODE", "auto") or "auto").strip().lower()
_DEFAULT_REFINE_RELAX_MIN_CLIPS = int(os.getenv("CLIP_RELAX_MIN_CLIPS", "5") or 5)
_DEFAULT_EXPAND_WINDOW_SECONDS = float(os.getenv("CLIP_EXPAND_WINDOW_SECONDS", "10") or 10)
_DEFAULT_TARGET_STRATEGY = str(os.getenv("CLIP_TARGET_STRATEGY", "density") or "density").strip().lower()


def _get_candidate_times(c: dict) -> tuple[float, float]:
    start = c.get("start_time")
    end = c.get("end_time")

    if start is None:
        start = c.get("start")
    if end is None:
        end = c.get("end")

    if start is None:
        start = c.get("startTime")
    if end is None:
        end = c.get("endTime")

    if start is None:
        start = c.get("start_seconds")
    if end is None:
        end = c.get("end_seconds")

    return float(start or 0), float(end or 0)


def _get_candidate_score_0_100(c: dict) -> float:
    if c.get("adjusted_engagement_score") is not None:
        return float(c.get("adjusted_engagement_score", 0) or 0)

    if c.get("score") is not None:
        raw = float(c.get("score", 0) or 0)
        return raw * 10.0 if raw <= 10 else raw

    engagement_score = float(c.get("engagement_score", 0) or 0)
    return engagement_score * 10.0 if engagement_score <= 10.0 else engagement_score


def _get_candidate_score_scaled(c: dict, *, scale_mode: str) -> float:
    raw = None
    if c.get("adjusted_engagement_score") is not None:
        raw = c.get("adjusted_engagement_score")
    elif c.get("score") is not None:
        raw = c.get("score")
    else:
        raw = c.get("engagement_score")

    try:
        val = float(raw or 0)
    except Exception:
        val = 0.0

    mode = (scale_mode or "auto").strip().lower()
    if mode == "0_10":
        return float(val * 10.0)
    if mode == "0_100":
        return float(val)

    if val <= 10.0:
        return float(val * 10.0)
    return float(val)


def _validate_and_normalize_config(config: dict) -> dict:
    min_duration = float(config.get("min_duration") or 0)
    max_duration = float(config.get("max_duration") or 0)
    if min_duration <= 0 or max_duration <= 0:
        raise ValueError("Config inválida: min_duration/max_duration devem ser > 0")
    if max_duration < min_duration:
        raise ValueError("Config inválida: max_duration deve ser >= min_duration")

    target_clips = int(config.get("target_clips") or 0)
    if target_clips <= 0:
        raise ValueError("Config inválida: target_clips deve ser >= 1")

    min_score = float(config.get("min_score") or 0)
    min_score = float(max(0.0, min(min_score, 100.0)))

    allow_overlapping = bool(config.get("allow_overlapping", False))
    overlap_ratio = float(config.get("overlap_ratio") or _DEFAULT_OVERLAP_RATIO)
    overlap_ratio = float(max(0.0, min(overlap_ratio, 1.0)))

    fallback_min_gap = float(config.get("fallback_min_gap") or _DEFAULT_FALLBACK_MIN_GAP)
    fallback_min_gap = float(max(0.0, fallback_min_gap))

    return {
        "min_duration": float(min_duration),
        "max_duration": float(max_duration),
        "target_clips": int(target_clips),
        "min_score": float(min_score),
        "allow_overlapping": bool(allow_overlapping),
        "overlap_ratio": float(overlap_ratio),
        "fallback_min_gap": float(fallback_min_gap),
    }


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_candidate(
    c: dict,
    *,
    ts_tolerance: float = _DEFAULT_CANDIDATE_TS_TOLERANCE,
    score_scale_mode: str = _DEFAULT_SCORE_SCALE_MODE,
) -> tuple[dict | None, str | None]:
    if not isinstance(c, dict):
        return None, "invalid_type"

    start, end = _get_candidate_times(c)
    if start < 0:
        start = 0.0
    if end < 0:
        end = 0.0

    if end <= start:
        if abs(end - start) <= float(ts_tolerance):
            return None, "zero_length"
        return None, "end_before_start"

    score = _safe_float(_get_candidate_score_scaled(c, scale_mode=score_scale_mode), default=0.0) or 0.0
    if score != score:
        return None, "invalid_score"
    if score == float("inf") or score == float("-inf"):
        return None, "invalid_score"
    score = float(max(0.0, min(score, 100.0)))

    text = c.get("text", "")
    if text is None:
        text = ""

    title = c.get("hook_title", "Viral Clip")
    if not title:
        title = "Viral Clip"

    return {
        "start_time": float(start),
        "end_time": float(end),
        "duration": float(end - start),
        "text": str(text),
        "title": str(title),
        "score": round(float(score), 2),
        "reasoning": str(c.get("reasoning", "") or ""),
        "_raw": c,
    }, None


def _normalize_candidates(candidates: list, *, score_scale_mode: str) -> tuple[list, dict]:
    out = []
    reasons: dict[str, int] = {}
    for c in candidates or []:
        norm, reason = _normalize_candidate(c, score_scale_mode=score_scale_mode)
        if not norm:
            key = str(reason or "invalid")
            reasons[key] = int(reasons.get(key, 0)) + 1
            continue
        out.append(norm)
    return out, reasons


def _prefilter_normalized(normalized: list, *, min_duration: float, max_duration: float) -> tuple[list, dict]:
    kept = []
    counts = {"filtered_duration": 0}
    for n in normalized or []:
        d = float(n.get("duration") or 0)
        if d < float(min_duration) or d > float(max_duration):
            counts["filtered_duration"] = int(counts["filtered_duration"]) + 1
            continue
        kept.append(n)
    return kept, counts


def _choose_target_clips(
    *,
    video_duration: float | None,
    min_duration: float,
    max_duration: float,
    min_target: int,
    max_target: int,
    strategy: str,
) -> int:
    if not video_duration or video_duration <= 0:
        return int(max(1, min(min_target, max_target)))

    st = (strategy or "density").strip().lower()
    if st == "fixed":
        return int(max(1, min(min_target, max_target)))

    mid = float(min_duration + (max_duration - min_duration) * 0.6)
    mid = float(max(1.0, mid))
    base = float(video_duration) / float(max(30.0, mid * _TARGET_ESTIMATE_FACTOR))
    est = int(max(1, round(base)))
    est = int(max(min_target, est))
    return int(min(est, max_target))


def _run_selection_stage(normalized: list, config: dict) -> tuple[list, dict]:
    raw = [n.get("_raw") or n for n in (normalized or [])]
    selected, stats = _process_selection(raw, config)
    return selected, stats


def _expand_from_segments(
    normalized: list,
    segments: list,
    *,
    min_duration: float,
    max_duration: float,
    video_duration: float,
    window_seconds: float,
) -> list:
    segs = [s for s in (segments or []) if isinstance(s, dict)]
    if not segs:
        out = []
        for n in normalized or []:
            start = float(n.get("start_time") or 0)
            end = float(n.get("end_time") or 0)
            if end <= start:
                end = start + float(min_duration)
            if video_duration and end > video_duration:
                end = float(video_duration)
            if end - start < float(min_duration):
                continue
            out.append({**n, "end_time": end, "duration": float(end - start)})
        return out

    try:
        segs.sort(key=lambda s: float(s.get("start") or 0))
    except Exception:
        pass

    expanded = []
    win = float(max(0.0, window_seconds))
    for n in normalized or []:
        start = float(n.get("start_time") or 0)
        base_end = float(n.get("end_time") or 0)
        if base_end <= start:
            base_end = start + float(min_duration)
        latest_end = start + float(max_duration)
        if video_duration and latest_end > video_duration:
            latest_end = float(video_duration)

        target_end = float(min(latest_end, max(base_end, start + float(min_duration))))
        desired_end = float(min(latest_end, start + float(min_duration + (max_duration - min_duration) * 0.6)))
        if desired_end > target_end:
            target_end = desired_end

        best_end = None
        end_min = float(max(start + float(min_duration), target_end - win))
        end_max = float(min(latest_end, target_end + win))

        for s in segs:
            e = _safe_float(s.get("end"), 0.0) or 0.0
            if e <= 0:
                continue
            if e >= end_min and e <= end_max:
                best_end = float(e)
                break

        if best_end is None:
            best_end = float(min(latest_end, max(target_end, start + float(min_duration))))

        if best_end - start < float(min_duration):
            continue
        if best_end - start > float(max_duration):
            continue

        parts = []
        for s in segs:
            ss = _safe_float(s.get("start"), 0.0) or 0.0
            ee = _safe_float(s.get("end"), 0.0) or 0.0
            if ee < start or ss > best_end:
                continue
            t = (s.get("text") or "").strip()
            if t:
                parts.append(t)

        txt = " ".join(parts).strip()
        if not txt:
            txt = (n.get("text") or "").strip()

        expanded.append({**n, "end_time": best_end, "duration": float(best_end - start), "text": txt})

    return expanded


@shared_task(bind=True, max_retries=3)
def select_clips_task(self, video_id: str) -> dict:
    try:
        logger.info(f"Iniciando seleção de clips para video_id: {video_id}")

        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)

        video.status = "selecting"
        video.current_step = "selecting"
        video.save()

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        analysis_data = transcript.analysis_data or {}
        candidates = analysis_data.get("candidates", [])

        if not candidates:
            msg = "Nenhum candidato de clip encontrado na análise"
            try:
                video.status = "failed"
                video.current_step = "selecting"
                video.error_message = msg
                video.save()
            except Exception:
                pass
            try:
                update_job_status(str(video.video_id), "failed", progress=100, current_step="selecting")
            except Exception:
                pass
            return {"error": msg, "status": "failed"}

        min_duration, max_duration = get_duration_bounds_from_job(video_id=video_id)
        min_duration = float(min_duration)
        max_duration = float(max_duration)
        if min_duration <= 0 or max_duration <= 0 or max_duration < min_duration:
            raise Exception(
                f"Bounds inválidos para duração: min_duration={min_duration} max_duration={max_duration}. "
                "Verifique as configurações do job e a duração do vídeo."
            )

        max_clips_desired = int(os.getenv("MAX_TARGET_CLIPS", "25") or 25)
        min_clips_desired = int(os.getenv("MIN_TARGET_CLIPS", "5") or 5)
        quality_threshold = 60.0
        allow_overlapping = False
        overlap_ratio = _DEFAULT_OVERLAP_RATIO
        fallback_min_gap = _DEFAULT_FALLBACK_MIN_GAP
        score_scale_mode = _DEFAULT_SCORE_SCALE_MODE
        relax_min_clips = int(_DEFAULT_REFINE_RELAX_MIN_CLIPS)
        target_strategy = _DEFAULT_TARGET_STRATEGY
        expand_window_seconds = float(_DEFAULT_EXPAND_WINDOW_SECONDS)
        try:
            from ..models import Job
            job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
            cfg = (job.configuration if job else None) or {}

            max_clips_desired = int(cfg.get("max_clips_desired") or cfg.get("maxClips") or max_clips_desired)
            min_clips_desired = int(cfg.get("min_clips_desired") or cfg.get("minClips") or min_clips_desired)
            quality_threshold = float(cfg.get("quality_threshold") or cfg.get("qualityThreshold") or quality_threshold)
            allow_overlapping = bool(cfg.get("allow_overlapping") or cfg.get("allowOverlapping") or False)
            overlap_ratio = float(cfg.get("overlap_ratio") or cfg.get("overlapRatio") or overlap_ratio)
            fallback_min_gap = float(cfg.get("fallback_min_gap") or cfg.get("fallbackMinGap") or fallback_min_gap)
            score_scale_mode = str(cfg.get("score_scale_mode") or cfg.get("scoreScaleMode") or score_scale_mode)
            relax_min_clips = int(cfg.get("relax_min_clips") or cfg.get("relaxMinClips") or relax_min_clips)
            target_strategy = str(cfg.get("target_strategy") or cfg.get("targetStrategy") or target_strategy)
            expand_window_seconds = float(cfg.get("expand_window_seconds") or cfg.get("expandWindowSeconds") or expand_window_seconds)
        except Exception as e:
            logger.warning("[select_clips] falha ao carregar config do Job (%s): %s", video_id, str(e))

        max_clips_desired = int(max(3, min(max_clips_desired, 25)))
        min_clips_desired = int(max(1, min(min_clips_desired, max_clips_desired)))
        quality_threshold = float(max(0.0, min(quality_threshold, 100.0)))

        target_clips = _choose_target_clips(
            video_duration=float(video.duration or 0) if video.duration else None,
            min_duration=float(min_duration),
            max_duration=float(max_duration),
            min_target=int(min_clips_desired),
            max_target=int(max_clips_desired),
            strategy=str(target_strategy),
        )

        config = _validate_and_normalize_config(
            {
                "max_duration": float(max_duration),
                "min_duration": float(min_duration),
                "target_clips": int(target_clips),
                "min_score": float(quality_threshold),
                "allow_overlapping": bool(allow_overlapping),
                "overlap_ratio": float(overlap_ratio),
                "fallback_min_gap": float(fallback_min_gap),
            }
        )

        normalized, invalid_reasons = _normalize_candidates(candidates, score_scale_mode=str(score_scale_mode))
        seed_norm, seed_counts = _prefilter_normalized(
            normalized,
            min_duration=5.0,
            max_duration=float(max_duration) * _DURATION_PREFILTER_SLACK,
        )
        pre_norm, pre_counts = _prefilter_normalized(
            seed_norm,
            min_duration=float(min_duration),
            max_duration=float(max_duration) * _DURATION_PREFILTER_SLACK,
        )

        logger.info(
            "[select_clips] bounds: min_duration=%ss max_duration=%ss | target_clips=%s | min_score=%s | allow_overlapping=%s | overlap_ratio=%s | candidates=%s seed=%s prefiltered=%s",
            int(config["min_duration"]),
            int(config["max_duration"]),
            int(config["target_clips"]),
            float(config["min_score"]),
            bool(config["allow_overlapping"]),
            float(config["overlap_ratio"]),
            len(candidates),
            len(seed_norm),
            len(pre_norm),
        )

        logger.info(
            "[select_clips] invalid_reasons=%s seed_filtered_duration=%s pre_filtered_duration=%s",
            dict(sorted(invalid_reasons.items(), key=lambda kv: (-kv[1], kv[0]))) if invalid_reasons else {},
            int(seed_counts.get("filtered_duration", 0)),
            int(pre_counts.get("filtered_duration", 0)),
        )

        pipeline = []
        pipeline.append(("initial", dict(config), pre_norm))

        if float(config["min_duration"]) > 5.0:
            expanded_norm = _expand_from_segments(
                seed_norm,
                segments=(transcript.segments or []),
                min_duration=float(config["min_duration"]),
                max_duration=float(config["max_duration"]),
                video_duration=float(video.duration or 0) if video.duration else 0.0,
                window_seconds=float(expand_window_seconds),
            )
            pipeline.append(("expanded", dict(config), expanded_norm))

        relax_min = int(max(1, min(relax_min_clips, max_clips_desired)))
        base_min_score = float(config.get("min_score") or 0)
        for step in list(_DEFAULT_RELAX_SCORE_STEPS):
            if float(step) >= base_min_score:
                continue
            cfg_step = dict(config)
            cfg_step["min_score"] = float(step)
            pipeline.append((f"relax_score_{int(step)}", cfg_step, pre_norm))

        cfg_overlap = dict(config)
        cfg_overlap["allow_overlapping"] = True
        cfg_overlap["overlap_ratio"] = _RELAXED_OVERLAP_RATIO
        pipeline.append(("relax_overlap", cfg_overlap, pre_norm))

        selected_clips = []
        merged = {
            "stage": None,
            "valid_candidates": 0,
            "filtered_duration": 0,
            "filtered_score": 0,
            "filtered_overlap": 0,
            "invalid": int(sum(invalid_reasons.values())) if invalid_reasons else 0,
        }

        for stage, cfg, norm_list in pipeline:
            cand, stats = _run_selection_stage(norm_list, cfg)
            merged["valid_candidates"] = int(max(merged["valid_candidates"], stats.get("valid_candidates", 0)))
            merged["filtered_duration"] = int(merged["filtered_duration"] + stats.get("filtered_duration", 0))
            merged["filtered_score"] = int(merged["filtered_score"] + stats.get("filtered_score", 0))
            merged["filtered_overlap"] = int(merged["filtered_overlap"] + stats.get("filtered_overlap", 0))
            merged["invalid"] = int(merged["invalid"] + stats.get("invalid", 0))

            if len(cand) > len(selected_clips):
                selected_clips = cand
                merged["stage"] = stage

            if len(selected_clips) >= relax_min:
                break

        logger.info(
            "[select_clips] stage=%s valid=%s filtered_duration=%s filtered_score=%s filtered_overlap=%s invalid=%s selected=%s",
            merged.get("stage"),
            merged.get("valid_candidates", 0),
            merged.get("filtered_duration", 0),
            merged.get("filtered_score", 0),
            merged.get("filtered_overlap", 0),
            merged.get("invalid", 0),
            len(selected_clips),
        )

        selected_clips = list(selected_clips)[:max_clips_desired]

        if not selected_clips:
            fallback = _fallback_select_any(
                [n.get("_raw") or n for n in seed_norm],
                config,
                video_duration=float(video.duration or 0) if video.duration else 0.0,
            )
            if fallback:
                selected_clips = fallback
                logger.info("[select_clips] stage=fallback selected=%s", len(selected_clips))
            else:
                raise Exception(
                    "Não foi possível selecionar clips com as regras atuais. "
                    f"Tente reduzir o quality_threshold ou ajustar os bounds de duração. "
                    f"duration_min={int(config['min_duration'])}s duration_max={int(config['max_duration'])}s "
                    f"candidates={len(candidates)} prefiltered={len(pre_norm)}"
                )

        transcript.selected_clips = selected_clips
        transcript.save()

        video.last_successful_step = "selecting"
        video.status = "reframing"
        video.current_step = "reframing"
        video.save()

        update_job_status(str(video.video_id), "reframing", progress=70, current_step="reframing")

        from .reframe_video_task import reframe_video_task
        reframe_video_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.reframe.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "selected_count": len(selected_clips),
            "top_score": selected_clips[0]["score"] if selected_clips else 0
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro na seleção {video_id}: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

            update_job_status(str(video.video_id), "failed", progress=100, current_step="selecting")

        msg = str(e)
        non_retryable = "Não foi possível selecionar" in msg

        if not non_retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _process_selection(candidates: list, config: dict):
    valid_candidates = []
    filtered_duration = 0
    filtered_score = 0
    filtered_overlap = 0
    invalid = 0

    for c in candidates or []:
        norm, reason = _normalize_candidate(c)
        if not norm:
            invalid += 1
            continue

        duration = float(norm["duration"])
        score = float(norm["score"])

        if duration < float(config["min_duration"]) or duration > float(config["max_duration"]):
            filtered_duration += 1
            continue

        if score < float(config["min_score"]):
            filtered_score += 1
            continue

        valid_candidates.append({
            "start_time": float(norm["start_time"]),
            "end_time": float(norm["end_time"]),
            "duration": float(norm["duration"]),
            "text": norm.get("text", ""),
            "title": norm.get("title", "Viral Clip"),
            "score": float(norm["score"]),
            "reasoning": norm.get("reasoning", ""),
        })

    valid_candidates.sort(key=lambda x: (-x["score"], x["start_time"], -(x["duration"])))

    final_selection = []

    allow_overlapping = bool(config.get("allow_overlapping", False))
    overlap_ratio = float(config.get("overlap_ratio", _DEFAULT_OVERLAP_RATIO) or _DEFAULT_OVERLAP_RATIO)

    for candidate in valid_candidates:
        if len(final_selection) >= config["target_clips"]:
            break

        if not allow_overlapping:
            is_overlapping = False
            for selected in final_selection:
                if _overlap_ratio(candidate, selected) >= overlap_ratio:
                    is_overlapping = True
                    break
            if is_overlapping:
                filtered_overlap += 1
                continue

        final_selection.append(candidate)

    stats = {
        "valid_candidates": len(valid_candidates),
        "filtered_duration": int(filtered_duration),
        "filtered_score": int(filtered_score),
        "filtered_overlap": int(filtered_overlap),
        "invalid": int(invalid),
    }

    return final_selection, stats


def _fallback_select_any(candidates: list, config: dict, *, video_duration: float) -> list:
    items = []
    for c in candidates or []:
        norm, reason = _normalize_candidate(c)
        if not norm:
            continue
        if norm["duration"] <= 0:
            continue
        items.append(
            {
                "start_time": float(norm["start_time"]),
                "end_time": float(norm["end_time"]),
                "duration": float(norm["duration"]),
                "text": norm.get("text", ""),
                "title": norm.get("title", "Viral Clip"),
                "score": float(norm["score"]),
                "reasoning": norm.get("reasoning", ""),
            }
        )

    if not items:
        return []

    items.sort(key=lambda x: (x["score"], -x["duration"], -x["end_time"]), reverse=True)

    min_d = float(config.get("min_duration") or 5)
    max_d = float(config.get("max_duration") or 90)
    target = int(config.get("target_clips") or 6)
    min_gap = float(config.get("fallback_min_gap") or _DEFAULT_FALLBACK_MIN_GAP)

    selected = []
    for it in items:
        if len(selected) >= target:
            break

        start = float(it["start_time"])
        end = start + float(min_d)
        if video_duration and end > video_duration:
            end = float(video_duration)
        if end - start < float(min_d):
            continue
        candidate = {
            **it,
            "end_time": float(end),
            "duration": float(end - start),
        }

        if any(abs(candidate["start_time"] - s["start_time"]) < min_gap for s in selected):
            continue

        selected.append(candidate)

    if not selected:
        best = items[0]
        start = float(best["start_time"])
        end = float(best["end_time"])
        dur = end - start
        if dur < min_d:
            end = start + min_d
        elif dur > max_d:
            end = start + max_d
        if video_duration and end > video_duration:
            end = float(video_duration)
        if end <= start:
            return []
        return [{**best, "end_time": float(end), "duration": float(end - start)}]

    return selected


def _overlap_ratio(clip_a: dict, clip_b: dict) -> float:
    start_a, end_a = float(clip_a["start_time"]), float(clip_a["end_time"])
    start_b, end_b = float(clip_b["start_time"]), float(clip_b["end_time"])

    intersection_start = max(start_a, start_b)
    intersection_end = min(end_a, end_b)
    if intersection_end <= intersection_start:
        return 0.0

    inter = intersection_end - intersection_start
    dur_a = max(0.001, end_a - start_a)
    dur_b = max(0.001, end_b - start_b)
    return float(inter / min(dur_a, dur_b))


def _pre_filter_candidates(candidates: list, min_duration: float, max_duration: float) -> list:
    out = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        start, end = _get_candidate_times(c)
        if end <= start:
            continue
        dur = end - start
        if dur < float(min_duration) or dur > float(max_duration):
            continue
        out.append(c)
    return out


def _expand_candidates_to_duration(
    candidates: list,
    segments: list,
    min_duration: float,
    max_duration: float,
    video_duration: float,
) -> list:
    if not candidates:
        return []

    segs = [s for s in (segments or []) if isinstance(s, dict)]
    if not segs:
        out = []
        for c in candidates:
            try:
                start = float(c.get("start_time", 0) or 0)
                end = start + float(min_duration)
                if video_duration and end > video_duration:
                    end = video_duration
                if end - start < float(min_duration):
                    continue
                out.append({**c, "end_time": end})
            except Exception:
                continue
        return out

    desired = float(min_duration + (max_duration - min_duration) * 0.6)
    if desired < float(min_duration):
        desired = float(min_duration)
    if desired > float(max_duration):
        desired = float(max_duration)

    def _seg_start(s):
        try:
            return float(s.get("start", 0) or 0)
        except Exception:
            return 0.0

    def _seg_end(s):
        try:
            return float(s.get("end", 0) or 0)
        except Exception:
            return 0.0

    segs.sort(key=_seg_start)

    expanded = []
    for c in candidates:
        try:
            start, _ = _get_candidate_times(c)
        except Exception:
            continue

        latest_end = start + float(max_duration)
        if video_duration and latest_end > video_duration:
            latest_end = video_duration

        target_end = start + desired
        if target_end > latest_end:
            target_end = latest_end

        chosen_end = None
        for s in segs:
            e = _seg_end(s)
            if e <= 0:
                continue
            if e >= target_end and e <= latest_end:
                chosen_end = e
                break

        if chosen_end is None:
            chosen_end = latest_end

        best_start = start
        latest_start = chosen_end - float(min_duration)
        earliest_start = chosen_end - float(max_duration)
        if earliest_start < 0:
            earliest_start = 0.0

        for s in reversed(segs):
            ss = _seg_start(s)
            if ss <= 0 and chosen_end <= 0:
                continue
            if ss <= start and ss <= latest_start and ss >= earliest_start:
                best_start = ss
                break

        duration = chosen_end - best_start
        if duration < float(min_duration) or duration > float(max_duration):
            continue

        parts = []
        for s in segs:
            ss = _seg_start(s)
            ee = _seg_end(s)
            if ee < best_start or ss > chosen_end:
                continue
            t = (s.get("text") or "").strip()
            if t:
                parts.append(t)

        expanded.append(
            {
                **c,
                "start_time": best_start,
                "end_time": chosen_end,
                "text": " ".join(parts) if parts else (c.get("text") or ""),
            }
        )

    return expanded


def _estimate_target_clips(video_duration: float | None, max_duration: int) -> int:
    try:
        if not video_duration or video_duration <= 0:
            return 6

        min_target = int(os.getenv("MIN_TARGET_CLIPS", "5") or 5)
        max_target = int(os.getenv("MAX_TARGET_CLIPS", "25") or 25)

        est = int(video_duration // max(15.0, (max_duration * _TARGET_ESTIMATE_FACTOR)))
        est = max(min_target, est)
        return min(est, max_target)
    except Exception:
        return 6
