import logging
import os
from typing import Optional, List, Dict, Any
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript, Organization
from .job_utils import get_plan_tier, update_job_status
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)

# Constantes configuráveis
DEFAULT_MAX_CHARS_PER_LINE = 25
DEFAULT_MIN_KARAOKE_CS = 1
DEFAULT_FONT_NAME = "Montserrat ExtraBold"
DEFAULT_FONT_SIZE = 60
DEFAULT_MARGIN_V = 150


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
        logger.warning(f"[caption] update_job_status failed for {video_id}: {e}")


def _to_float(x, default: float = 0.0) -> float:
    """Conversão segura para float"""
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


@shared_task(bind=True, max_retries=5)
def caption_clips_task(self, video_id: str) -> dict:
    """
    Gera legendas karaoke em formato ASS para cada clip selecionado
    
    Fluxo:
    1. Valida vídeo e transcrição
    2. Para cada clip selecionado, gera arquivo .ass
    3. Salva referências dos arquivos
    4. Dispara próxima task (rendering)
    """
    video = None
    
    try:
        logger.info(f"[caption] Iniciando para video_id={video_id}")
        
        # Carrega vídeo e organização
        video = Video.objects.get(video_id=video_id)
        org = Organization.objects.get(organization_id=video.organization_id)
        
        # Atualiza status
        video.status = "captioning"
        video.current_step = "captioning"
        video.save()

        # Valida transcrição
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise ValueError("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        if not selected_clips:
            raise ValueError("Nenhum clip selecionado para gerar legendas")

        # Prepara diretório de saída
        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        storage = R2StorageService()
        existing_caption_files = transcript.caption_files or []
        kept_caption_files = [c for c in existing_caption_files if isinstance(c, dict) and str(c.get("kind") or "").lower() != "ass"]

        caption_files: List[Dict[str, Any]] = []
        total_clips = max(1, len(selected_clips))
        
        logger.info(f"[caption] Gerando legendas para {total_clips} clips")
        
        for idx, clip in enumerate(selected_clips):
            # Calcula progress de forma segura (85-95%)
            progress_pct = 85 + int((idx / total_clips) * 10)
            progress_pct = int(max(85, min(progress_pct, 95)))
            
            _safe_update_job_status(
                str(video.video_id),
                "captioning",
                progress=progress_pct,
                current_step=f"captioning_clip_{idx+1}/{total_clips}",
            )
            
            # Extrai timestamps do clip
            clip_start = _to_float(clip.get("start_time"), 0.0)
            clip_end = _to_float(clip.get("end_time"), 0.0)
            
            if clip_end <= clip_start:
                logger.warning(
                    f"[caption] Clip {idx} tem timestamps inválidos: "
                    f"start={clip_start} end={clip_end}, pulando"
                )
                continue

            # Gera arquivo ASS
            ass_filename = f"caption_{idx}.ass"
            ass_path = os.path.join(output_dir, ass_filename)
            
            try:
                _generate_karaoke_ass(
                    transcript=transcript,
                    clip_start=clip_start,
                    clip_end=clip_end,
                    output_file=ass_path,
                )
            except Exception as e:
                logger.error(f"[caption] Falha ao gerar ASS para clip {idx}: {e}")
                continue

            # Valida arquivo gerado
            if not os.path.exists(ass_path):
                logger.warning(f"[caption] ASS não foi criado para clip {idx}")
                continue
                
            file_size = os.path.getsize(ass_path)
            if file_size <= 0:
                logger.warning(f"[caption] ASS vazio para clip {idx}")
                try:
                    os.remove(ass_path)
                except Exception:
                    pass
                continue

            logger.debug(
                f"[caption] ASS gerado para clip {idx}: "
                f"{ass_filename} ({file_size} bytes)"
            )

            clip_id = str(clip.get("clip_id") or clip.get("id") or clip.get("clipId") or idx)
            if not clip_id:
                clip_id = str(idx)

            storage_path = None
            try:
                storage_path = storage.upload_caption(
                    file_path=ass_path,
                    organization_id=str(video.organization_id),
                    video_id=str(video.video_id),
                    clip_id=str(clip_id),
                )
            except Exception as e:
                logger.error(f"[caption] Falha ao fazer upload ASS para clip {idx}: {e}")
                continue

            caption_files.append({
                "kind": "ass",
                "index": idx,
                "clip_id": str(clip_id),
                "path": str(storage_path),
                "start_time": float(clip_start),
                "end_time": float(clip_end),
                "file_size": int(file_size),
            })

        # Valida se gerou pelo menos uma legenda
        if not caption_files:
            logger.warning(f"[caption] Nenhuma legenda gerada para video_id={video_id}")
            # Não falha - pode continuar sem legendas se configurado assim
            # raise ValueError("Nenhuma legenda foi gerada com sucesso")

        merged = kept_caption_files + caption_files
        transcript.caption_files = merged
        transcript.save()

        logger.info(
            f"[caption] Concluído para video_id={video_id}: "
            f"{len(caption_files)}/{total_clips} legendas geradas"
        )

        # Atualiza status e dispara próxima task
        video.last_successful_step = "captioning"
        video.status = "rendering"
        video.current_step = "rendering"
        video.save()
        
        _safe_update_job_status(
            str(video.video_id),
            "rendering",
            progress=90,
            current_step="rendering"
        )

        from .clip_generation_task import clip_generation_task
        clip_generation_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.clip.{get_plan_tier(org.plan)}",
        )

        return {
            "video_id": str(video.video_id),
            "captions_generated": len(caption_files),
            "captions_failed": total_clips - len(caption_files),
            "status": "success",
        }

    except Video.DoesNotExist:
        logger.error(f"[caption] Video not found: {video_id}")
        return {"error": "Video not found", "status": "failed"}
        
    except Exception as e:
        logger.error(f"[caption] Error for video_id={video_id}: {e}", exc_info=True)
        
        if video:
            video.status = "failed"
            video.error_message = str(e)
            video.save()

            _safe_update_job_status(
                str(video.video_id),
                "failed",
                progress=100,
                current_step="captioning"
            )

        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            logger.info(
                f"[caption] Retrying ({self.request.retries + 1}/{self.max_retries}) "
                f"in {countdown}s"
            )
            raise self.retry(exc=e, countdown=countdown)

        return {"error": str(e), "status": "failed"}


def _generate_karaoke_ass(
    transcript: "Transcript",
    clip_start: float,
    clip_end: float,
    output_file: str,
) -> None:
    """
    Gera arquivo ASS com legendas karaoke para um clip
    
    Args:
        transcript: Objeto Transcript com segments e words
        clip_start: Tempo de início do clip (segundos)
        clip_end: Tempo de fim do clip (segundos)
        output_file: Path do arquivo ASS a ser criado
        
    Raises:
        ValueError: Se parâmetros inválidos
        IOError: Se não conseguir escrever arquivo
    """
    # Validação de parâmetros
    if clip_end <= clip_start:
        raise ValueError(
            f"Timestamps inválidos: start={clip_start} end={clip_end}"
        )
    
    segments = transcript.segments or []
    if not segments:
        raise ValueError("Transcrição sem segments")

    # Configurações
    font_name = _get_config("CAPTION_FONT_NAME", DEFAULT_FONT_NAME, str)
    font_size = _get_config("CAPTION_FONT_SIZE", DEFAULT_FONT_SIZE, int)
    margin_v = _get_config("CAPTION_MARGIN_V", DEFAULT_MARGIN_V, int)
    max_chars_per_line = _get_config("CAPTION_MAX_CHARS_PER_LINE", DEFAULT_MAX_CHARS_PER_LINE, int)
    min_karaoke_cs = _get_config("CAPTION_MIN_KARAOKE_CS", DEFAULT_MIN_KARAOKE_CS, int)

    # Valida configurações
    font_size = int(max(20, min(font_size, 200)))
    margin_v = int(max(0, min(margin_v, 1000)))
    max_chars_per_line = int(max(10, min(max_chars_per_line, 100)))
    min_karaoke_cs = int(max(1, min(min_karaoke_cs, 100)))

    # Header ASS
    header = f"""[Script Info]
Title: Klipai Karaoke
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: List[str] = []
    segments_used = 0
    words_used = 0

    # Processa cada segment
    for seg in segments:
        if not isinstance(seg, dict):
            continue

        seg_start = _to_float(seg.get("start"), 0.0)
        seg_end = _to_float(seg.get("end"), 0.0)
        
        # Pula segments fora do clip
        if seg_end < clip_start or seg_start > clip_end:
            continue
        
        segments_used += 1
            
        words = seg.get("words", [])
        
        # Validação de words array
        if not isinstance(words, list):
            words = []
            
        # Fallback: segment sem words
        if not words:
            # Calcula timestamps relativos ao clip
            rel_start = max(0.0, seg_start - clip_start)
            rel_end = min(clip_end - clip_start, seg_end - clip_start)
            
            if rel_end > rel_start:
                start_time_str = _seconds_to_ass_time(rel_start)
                end_time_str = _seconds_to_ass_time(rel_end)
                
                text = (seg.get("text") or "").strip()
                if text:
                    text_escaped = _escape_ass_text(text.upper())
                    events.append(
                        f"Dialogue: 0,{start_time_str},{end_time_str},"
                        f"Default,,0,0,0,,{text_escaped}"
                    )
            continue

        # Processa words com karaoke
        current_line_words: List[Dict[str, Any]] = []
        current_chars = 0
        
        for word in words:
            if not isinstance(word, dict):
                continue

            word_text = (word.get("word") or "").strip()
            if not word_text:
                continue

            word_start = _to_float(word.get("start"), 0.0)
            word_end = _to_float(word.get("end"), 0.0)
            
            # Valida timestamps da palavra
            if word_end <= word_start:
                continue
            
            # Calcula timestamps relativos ao clip
            rel_w_start = word_start - clip_start
            rel_w_end = word_end - clip_start
            
            # Pula palavras fora do clip
            if rel_w_end < 0 or rel_w_start > (clip_end - clip_start):
                continue

            words_used += 1

            # Calcula duração em centisegundos
            duration_s = word_end - word_start
            duration_cs = int(duration_s * 100)
            duration_cs = max(min_karaoke_cs, duration_cs)

            current_line_words.append({
                "text": word_text,
                "start": rel_w_start,
                "end": rel_w_end,
                "duration_cs": duration_cs,
            })
            
            current_chars += len(word_text) + 1  # +1 para espaço
            
            # Quebra linha se atingir limite de caracteres
            should_break_line = (
                current_chars >= max_chars_per_line or
                _is_sentence_end(word_text)
            )
            
            if should_break_line and current_line_words:
                _add_karaoke_event(events, current_line_words)
                current_line_words = []
                current_chars = 0
        
        # Adiciona linha final se houver palavras restantes
        if current_line_words:
            _add_karaoke_event(events, current_line_words)

    logger.debug(
        f"[caption] ASS gerado: {segments_used} segments, "
        f"{words_used} words, {len(events)} events"
    )

    # Escreve arquivo
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(header)
            if events:
                f.write("\n".join(events))
    except IOError as e:
        logger.error(f"[caption] Falha ao escrever arquivo ASS: {e}")
        raise


def _add_karaoke_event(events_list: List[str], words_data: List[Dict[str, Any]]) -> None:
    """
    Adiciona um evento de karaoke à lista
    
    Args:
        events_list: Lista de eventos ASS (modificada in-place)
        words_data: Lista de palavras com timing
    """
    if not words_data:
        return

    # Extrai timestamps
    start_time = _to_float(words_data[0].get("start"), 0.0)
    end_time = _to_float(words_data[-1].get("end"), 0.0)
    
    if end_time <= start_time:
        logger.warning("[caption] Evento karaoke com timestamps inválidos, pulando")
        return
    
    start_time_str = _seconds_to_ass_time(start_time)
    end_time_str = _seconds_to_ass_time(end_time)
    
    # Monta texto com tags karaoke
    text_parts: List[str] = []
    
    for word in words_data:
        word_text = (word.get("text") or "").strip()
        if not word_text:
            continue
            
        duration_cs = int(word.get("duration_cs", 1) or 1)
        duration_cs = max(1, duration_cs)  # Garante mínimo de 1cs
        
        text_escaped = _escape_ass_text(word_text.upper())
        text_parts.append(f"{{\\k{duration_cs}}}{text_escaped}")
    
    if not text_parts:
        return
        
    full_text = " ".join(text_parts)
    
    events_list.append(
        f"Dialogue: 0,{start_time_str},{end_time_str},"
        f"Default,,0,0,0,,{full_text}"
    )


def _seconds_to_ass_time(seconds: float) -> str:
    """
    Converte segundos para formato de tempo ASS (H:MM:SS.CS)
    
    Args:
        seconds: Tempo em segundos
        
    Returns:
        String formatada (ex: "0:01:23.45")
    """
    if seconds < 0:
        seconds = 0.0
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    
    # Limita valores
    hours = min(hours, 9)  # ASS usa 1 dígito para horas
    centisecs = min(centisecs, 99)
    
    return f"{hours:1d}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def _escape_ass_text(text: str) -> str:
    
    if not isinstance(text, str):
        return ""
    
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("{", "\\{")
    escaped = escaped.replace("}", "\\}")
    
    escaped = escaped.replace("\n", " ").replace("\r", " ")
    
    while "  " in escaped:
        escaped = escaped.replace("  ", " ")
    
    return escaped.strip()


def _is_sentence_end(text: str) -> bool:

    if not isinstance(text, str):
        return False
        
    end_punctuation = ('.', '?', '!', ':', ';', '…')
    
    return text.rstrip().endswith(end_punctuation)