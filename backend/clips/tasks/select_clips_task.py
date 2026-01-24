import logging
from celery import shared_task
import os

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status

logger = logging.getLogger(__name__)


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
    return engagement_score * 10.0


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
            raise Exception("Nenhum candidato de clip encontrado na análise")

        min_duration, max_duration = _get_duration_bounds(video_id=video_id)

        # Job.configuration overrides (optional)
        max_clips_desired = int(os.getenv("MAX_TARGET_CLIPS", "25") or 25)
        min_clips_desired = int(os.getenv("MIN_TARGET_CLIPS", "5") or 5)
        quality_threshold = 60.0
        allow_overlapping = False
        try:
            from ..models import Job
            job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
            cfg = (job.configuration if job else None) or {}

            max_clips_desired = int(cfg.get("max_clips_desired") or cfg.get("maxClips") or max_clips_desired)
            min_clips_desired = int(cfg.get("min_clips_desired") or cfg.get("minClips") or min_clips_desired)
            quality_threshold = float(cfg.get("quality_threshold") or cfg.get("qualityThreshold") or quality_threshold)
            allow_overlapping = bool(cfg.get("allow_overlapping") or cfg.get("allowOverlapping") or False)
        except Exception:
            pass

        max_clips_desired = int(max(3, min(max_clips_desired, 25)))
        min_clips_desired = int(max(1, min(min_clips_desired, max_clips_desired)))
        quality_threshold = float(max(0.0, min(quality_threshold, 100.0)))

        target_clips = _estimate_target_clips(video_duration=video.duration, max_duration=max_duration)
        target_clips = int(max(min_clips_desired, min(target_clips, max_clips_desired)))

        seed_candidates = _pre_filter_candidates(
            candidates,
            min_duration=5.0,
            max_duration=float(max_duration) * 1.10,
        )

        prefiltered = _pre_filter_candidates(
            seed_candidates,
            min_duration=float(min_duration),
            max_duration=float(max_duration) * 1.10,
        )

        config = {
            "max_duration": int(max_duration),
            "min_duration": int(min_duration),
            "target_clips": int(target_clips),
            "min_score": float(quality_threshold),
            "allow_overlapping": bool(allow_overlapping),
            "overlap_ratio": 0.75,
        }

        selected_clips = _process_selection(prefiltered, config)

        if not selected_clips and float(min_duration) > 5.0:
            expanded = _expand_candidates_to_duration(
                seed_candidates,
                segments=(transcript.segments or []),
                min_duration=float(min_duration),
                max_duration=float(max_duration),
                video_duration=float(video.duration or 0) if video.duration else 0.0,
            )
            selected_clips = _process_selection(expanded, config)

        if not selected_clips and int(min_duration) >= 45:
            expanded = _expand_candidates_to_duration(
                seed_candidates,
                segments=(transcript.segments or []),
                min_duration=float(min_duration),
                max_duration=float(max_duration),
                video_duration=float(video.duration or 0) if video.duration else 0.0,
            )
            selected_clips = _process_selection(expanded, config)

        # Progressive relaxation ONLY if we found too few (avoid constant degradation)
        if len(selected_clips) < min(5, min_clips_desired):
            logger.warning(
                "Selecionou apenas %s clips (<%s). Relaxando regras progressivamente...",
                len(selected_clips),
                min(5, min_clips_desired),
            )

            # 1) Relax score threshold
            config_1 = dict(config)
            config_1["min_score"] = min(config_1["min_score"], 40.0)
            selected_1 = _process_selection(prefiltered, config_1)
            if len(selected_1) > len(selected_clips):
                selected_clips = selected_1

            # 2) Relax duration (slightly)
            if len(selected_clips) < min(5, min_clips_desired):
                config_2 = dict(config_1)
                # Never relax below the user-configured minimum duration.
                config_2["min_duration"] = int(min_duration)
                config_2["max_duration"] = int(max(config_2["max_duration"], max(90, int(max_duration * 1.2))))
                selected_2 = _process_selection(prefiltered, config_2)
                if len(selected_2) > len(selected_clips):
                    selected_clips = selected_2

            # 3) Relax overlap
            if len(selected_clips) < min(5, min_clips_desired):
                config_3 = dict(config_2 if "config_2" in locals() else config_1)
                config_3["allow_overlapping"] = True
                config_3["overlap_ratio"] = 0.92
                selected_3 = _process_selection(prefiltered, config_3)
                if len(selected_3) > len(selected_clips):
                    selected_clips = selected_3

            # Final fallback: always return something
            if not selected_clips:
                selected_clips = _fallback_select_any(
                    (prefiltered or seed_candidates or candidates),
                    {
                        **config,
                        "min_score": -1,
                        "min_duration": int(min_duration),
                    },
                )

        # Hardcap max clips
        selected_clips = list(selected_clips)[:max_clips_desired]

        if not selected_clips:
            raise Exception("Não foi possível selecionar nenhum clip válido")

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
        non_retryable = "Não foi possível selecionar nenhum clip válido" in msg

        if not non_retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _process_selection(candidates: list, config: dict) -> list:
    valid_candidates = []

    for c in candidates:
        start, end = _get_candidate_times(c)
        duration = end - start
        
        score = round(float(_get_candidate_score_0_100(c)), 2)
        
        logger.debug(f"Candidato: start={start}, end={end}, duration={duration}s, score={score}/100")
        
        if duration < float(config["min_duration"]) or duration > float(config["max_duration"]):
            logger.debug(f"  ❌ Duração fora do intervalo ({config['min_duration']}-{config['max_duration']}s)")
            continue
            
        if score < float(config["min_score"]):
            logger.debug(f"  ❌ Score baixo (min: {config['min_score']}/100)")
            continue

        logger.debug(f"  ✅ Candidato válido")
        valid_candidates.append({
            "start_time": start,
            "end_time": end,
            "duration": duration,
            "text": c.get("text", ""),
            "title": c.get("hook_title", "Viral Clip"),
            "score": score, 
            "reasoning": c.get("reasoning", "")
        })

    valid_candidates.sort(key=lambda x: x["score"], reverse=True)

    final_selection = []
    
    allow_overlapping = bool(config.get("allow_overlapping", False))
    overlap_ratio = float(config.get("overlap_ratio", 0.75) or 0.75)

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
                continue

        final_selection.append(candidate)
            
    return final_selection


def _fallback_select_any(candidates: list, config: dict) -> list:
    """Último recurso: sempre retornar algo razoável.

    Estratégia:
    - Converte candidatos em formato interno.
    - Ordena por score.
    - Seleciona respeitando uma distância mínima entre clips.
    - Se precisar, ajusta (clamp) a duração para ficar dentro de min/max.
    """
    try:
        items = []
        for c in candidates:
            start, end = _get_candidate_times(c)
            if end <= start:
                continue

            score = float(_get_candidate_score_0_100(c))

            items.append(
                {
                    "start_time": start,
                    "end_time": end,
                    "duration": end - start,
                    "text": c.get("text", ""),
                    "title": c.get("hook_title", "Viral Clip"),
                    "score": round(float(score), 2),
                    "reasoning": c.get("reasoning", ""),
                }
            )

        if not items:
            return []

        items.sort(key=lambda x: x["score"], reverse=True)

        min_d = float(config.get("min_duration") or 5)
        max_d = float(config.get("max_duration") or 90)
        target = int(config.get("target_clips") or 6)

        # distância mínima (em segundos) entre clips no fallback
        min_gap = float(config.get("fallback_min_gap", 3.0) or 3.0)

        selected = []
        for it in items:
            if len(selected) >= target:
                break

            # Ajusta duração para não descartar tudo
            start = float(it["start_time"])
            end = float(it["end_time"])
            dur = end - start

            if dur < min_d:
                end = start + min_d
            elif dur > max_d:
                end = start + max_d

            candidate = {
                **it,
                "end_time": end,
                "duration": end - start,
            }

            # garante espaçamento mínimo
            if any(abs(candidate["start_time"] - s["start_time"]) < min_gap for s in selected):
                continue

            selected.append(candidate)

        # Se ainda vazio, pega o melhor mesmo sem gap
        if not selected:
            best = items[0]
            start = float(best["start_time"])
            end = float(best["end_time"])
            dur = end - start
            if dur < min_d:
                end = start + min_d
            elif dur > max_d:
                end = start + max_d
            return [{**best, "end_time": end, "duration": end - start}]

        return selected
    except Exception:
        return []


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
        try:
            start, end = _get_candidate_times(c)
            if end <= start:
                continue
            dur = end - start
            if dur < float(min_duration) or dur > float(max_duration):
                continue
            out.append(c)
        except Exception:
            continue
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


def _get_duration_bounds(video_id: str) -> tuple[int, int]:
    """Busca min/max duration a partir de Job.configuration quando existir.

    Compatível com:
    - job.configuration.max_clip_duration
    - job.configuration.maxDuration
    - defaults
    """
    try:
        from ..models import Job
        job = Job.objects.filter(video_id=video_id).order_by("-created_at").first()
        cfg = (job.configuration if job else None) or {}

        max_d = cfg.get("max_clip_duration") or cfg.get("maxDuration")
        if max_d is None:
            max_d = 60

        max_d = int(max(10, min(int(max_d), 180)))

        min_d = cfg.get("min_clip_duration") or cfg.get("minDuration")
        if min_d is None:
            min_d = max(10, int(round(max_d * 0.6)))

        min_d = int(max(5, min(int(min_d), max_d)))
        return min_d, max_d
    except Exception:
        return 10, 60


def _estimate_target_clips(video_duration: float | None, max_duration: int) -> int:
    try:
        if not video_duration or video_duration <= 0:
            return 6

        min_target = int(os.getenv("MIN_TARGET_CLIPS", "10") or 10)
        max_target = int(os.getenv("MAX_TARGET_CLIPS", "40") or 40)

        est = int(video_duration // max(15.0, (max_duration * 1.8)))
        est = max(min_target, est)
        return min(est, max_target)
    except Exception:
        return 6
