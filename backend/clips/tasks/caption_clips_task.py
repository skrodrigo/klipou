import logging
import os
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript, Organization
from .job_utils import update_job_status

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def caption_clips_task(self, video_id: str) -> dict:
    try:
        logger.info(f"Iniciando geração de legendas Karaoke para: {video_id}")
        
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "captioning"
        video.current_step = "captioning"
        video.save()

        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        if not selected_clips:
            raise Exception("Nenhum clip selecionado")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        caption_files = []
        
        for idx, clip in enumerate(selected_clips):
            update_job_status(str(video.video_id), "captioning", progress=85 + idx, current_step=f"captioning_clip_{idx+1}")
            
            clip_start = clip.get("start_time", 0)
            clip_end = clip.get("end_time", 0)

            ass_filename = f"caption_{idx}.ass"
            ass_path = os.path.join(output_dir, ass_filename)
            
            _generate_karaoke_ass(
                transcript=transcript,
                clip_start=clip_start,
                clip_end=clip_end,
                output_file=ass_path,
            )

            caption_files.append({
                "index": idx,
                "ass_file": ass_path,
                "start_time": clip_start,
                "end_time": clip_end,
            })

        transcript.caption_files = caption_files
        transcript.save()

        video.last_successful_step = "captioning"
        video.status = "rendering"
        video.current_step = "rendering"
        video.save()
        
        update_job_status(str(video.video_id), "rendering", progress=90, current_step="rendering")

        from .clip_generation_task import clip_generation_task
        clip_generation_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.clip.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "captions_generated": len(caption_files),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro captioning {video_id}: {e}", exc_info=True)
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _generate_karaoke_ass(
    transcript: "Transcript",
    clip_start: float,
    clip_end: float,
    output_file: str,
) -> None:
    segments = transcript.segments or []

    header = """[Script Info]
Title: Klipai Karaoke
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat ExtraBold,60,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,20,20,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    for seg in segments:
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        
        if seg_end < clip_start or seg_start > clip_end:
            continue
            
        words = seg.get("words", [])
        if not words:
            rel_start = max(0, seg_start - clip_start)
            rel_end = min(clip_end - clip_start, seg_end - clip_start)
            
            if rel_end > rel_start:
                start_s = _seconds_to_ass_time(rel_start)
                end_s = _seconds_to_ass_time(rel_end)
                text = (seg.get("text") or "").strip().upper()
                events.append(f"Dialogue: 0,{start_s},{end_s},Default,,0,0,0,,{text}")
            continue

        current_line_words = []
        current_chars = 0
        MAX_CHARS_PER_LINE = 25
        
        for w in words:
            word_text = w.get("word", "").strip()
            word_start = w.get("start", 0)
            word_end = w.get("end", 0)
            
            rel_w_start = word_start - clip_start
            rel_w_end = word_end - clip_start
            
            if rel_w_end < 0 or rel_w_start > (clip_end - clip_start):
                continue

            current_line_words.append({
                "text": word_text,
                "start": rel_w_start,
                "end": rel_w_end,
                "duration_cs": int((word_end - word_start) * 100)
            })
            
            current_chars += len(word_text) + 1
            
            if current_chars >= MAX_CHARS_PER_LINE or word_text.endswith(('.', '?', '!')):
                _add_karaoke_event(events, current_line_words)
                current_line_words = []
                current_chars = 0
        
        if current_line_words:
            _add_karaoke_event(events, current_line_words)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))


def _add_karaoke_event(events_list, words_data):
    if not words_data:
        return

    start_time = words_data[0]["start"]
    end_time = words_data[-1]["end"]
    
    start_s = _seconds_to_ass_time(start_time)
    end_s = _seconds_to_ass_time(end_time)
    
    text_parts = []
    for w in words_data:
        clean_text = w["text"].upper()
        duration = w["duration_cs"]
        text_parts.append(f"{{\\k{duration}}}{clean_text}")
        
    full_text = " ".join(text_parts)
    
    events_list.append(f"Dialogue: 0,{start_s},{end_s},Default,,0,0,0,,{full_text}")


def _seconds_to_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    
    return f"{hours:1d}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
