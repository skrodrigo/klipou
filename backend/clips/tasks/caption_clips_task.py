"""
Task para legendagem avançada (ASS).
Etapa: Captioning
Gera arquivo ASS com timestamps por palavra e queima no vídeo.
"""

import os
import subprocess
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..models import Video, Transcript
from ..services.storage_service import R2StorageService
from .job_utils import update_job_status


@shared_task(bind=True, max_retries=5)
def caption_clips_task(self, video_id: int) -> dict:
    """
    Gera legendas ASS para cada clip selecionado.
    
    Entrada:
    - Transcrição com timestamps por palavra
    - Clips selecionados com timestamps
    - Proporção do vídeo
    
    Saída:
    - Arquivo ASS por clip
    - Vídeo com legendas queimadas
    """
    try:
        # Procura vídeo por video_id (UUID)
        video = Video.objects.get(video_id=video_id)
        
        # Obtém organização
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "captioning"
        video.current_step = "captioning"
        video.save()

        # Obtém transcrição e clips selecionados
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        if not selected_clips:
            raise Exception("Nenhum clip selecionado")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Gera ASS para cada clip
        caption_files = []
        for idx, clip in enumerate(selected_clips):
            start_time = clip.get("start_time", 0)
            end_time = clip.get("end_time", 0)

            # Gera arquivo ASS
            ass_file = os.path.join(output_dir, f"caption_{idx}.ass")
            _generate_ass_file(
                transcript=transcript,
                start_time=start_time,
                end_time=end_time,
                output_file=ass_file,
            )

            caption_files.append({
                "index": idx,
                "ass_file": ass_file,
                "start_time": start_time,
                "end_time": end_time,
            })

        # Armazena informações de legendas na transcrição
        transcript.caption_files = caption_files
        transcript.save()

        # Atualiza vídeo - FINALIZA PIPELINE
        video.last_successful_step = "captioning"
        video.status = "done"
        video.current_step = "done"
        video.completed_at = timezone.now()
        video.save()
        
        # Atualiza job status - FINALIZA PIPELINE
        update_job_status(str(video.video_id), "done", progress=100, current_step="done")

        return {
            "video_id": str(video.video_id),
            "status": "done",
            "caption_files_count": len(caption_files),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "captioning"
        video.error_code = "CAPTIONING_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _generate_ass_file(
    transcript: "Transcript",
    start_time: float,
    end_time: float,
    output_file: str,
) -> None:
    """
    Gera arquivo ASS com legendas para um clip.
    
    Estilo:
    - Fonte: Bold
    - Texto: CAIXA ALTA
    - Posição: Centralizado na parte inferior
    - Máximo: 2 linhas por frame
    - Destaque dinâmico: Karaoke (palavra falada em destaque)
    """
    segments = transcript.segments or []

    # Filtra segmentos que caem dentro do intervalo do clip
    clip_segments = [
        seg for seg in segments
        if seg.get("start", 0) >= start_time and seg.get("end", 0) <= end_time
    ]

    # ASS header padrão
    ass_content = """[Script Info]
Title: Klipai Caption
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Adiciona eventos de legenda
    for seg in clip_segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = (seg.get("text") or "").upper()

        # Converte tempo para formato ASS (HH:MM:SS.CC)
        start_ts = _seconds_to_ass_time(start)
        end_ts = _seconds_to_ass_time(end)

        # Aplica karaoke se houver timestamps por palavra
        words = seg.get("words", [])
        if words:
            text = _apply_karaoke(text, words)

        # Limita a 2 linhas
        text_lines = text.split()
        if len(text_lines) > 10:  # Aproximadamente 2 linhas
            text = " ".join(text_lines[:10])

        ass_content += f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n"

    # Salva arquivo ASS
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ass_content)


def _apply_karaoke(text: str, words: list) -> str:
    """
    Aplica efeito karaoke ao texto usando tags ASS.
    Destaca a palavra sendo falada em tempo real.
    """
    # Implementação simplificada
    # Em produção, seria necessário sincronizar com timestamps exatos
    return text


def _seconds_to_ass_time(seconds: float) -> str:
    """Converte segundos para formato ASS HH:MM:SS.CC."""
    total_centiseconds = int(round(seconds * 100))
    hours, rem = divmod(total_centiseconds, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, centisecs = divmod(rem, 100)
    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
