"""
Task para geração de clips finais.
Etapa: Clipping
Corta vídeo original nos timestamps selecionados com legendas queimadas.
"""

import os
import uuid
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Clip, Transcript
from .job_utils import update_job_status
from ..services.storage_service import R2StorageService


@shared_task(bind=True, max_retries=5)
def clip_generation_task(self, video_id: int) -> dict:
    """
    Gera clips finais com FFmpeg.
    
    Para cada clip selecionado:
    1. Corta vídeo nos timestamps
    2. Aplica legenda ASS queimada
    3. Normaliza áudio
    4. Exporta em MP4
    5. Faz upload para R2
    """
    try:
        # Procura vídeo por video_id (UUID)
        video = Video.objects.get(video_id=video_id)
        
        # Obtém organização
        from ..models import Organization
        org = Organization.objects.get(organization_id=video.organization_id)
        
        video.status = "clipping"
        video.current_step = "clipping"
        video.save()

        # Obtém transcrição e clips selecionados
        transcript = Transcript.objects.filter(video=video).first()
        if not transcript:
            raise Exception("Transcrição não encontrada")

        selected_clips = transcript.selected_clips or []
        caption_files = transcript.caption_files or []

        if not selected_clips:
            raise Exception("Nenhum clip selecionado")

        output_dir = os.path.join(settings.MEDIA_ROOT, f"videos/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        # Arquivo normalizado da etapa anterior
        input_path = os.path.join(output_dir, "video_normalized.mp4")

        if not os.path.exists(input_path):
            raise Exception("Arquivo de vídeo normalizado não encontrado")

        # Gera cada clip
        storage = R2StorageService()
        generated_clips = []

        for idx, clip in enumerate(selected_clips):
            start_time = clip.get("start_time", 0)
            end_time = clip.get("end_time", 0)
            hook_title = clip.get("hook_title", f"Clip {idx + 1}")

            # Arquivo ASS correspondente
            ass_file = None
            for cap in caption_files:
                if cap.get("index") == idx:
                    ass_file = cap.get("ass_file")
                    break

            # Gera clip com FFmpeg
            clip_path = os.path.join(output_dir, f"clip_{idx}.mp4")
            _generate_clip_with_ffmpeg(
                input_path=input_path,
                output_path=clip_path,
                start_time=start_time,
                end_time=end_time,
                ass_file=ass_file,
            )

            # Faz upload para R2
            clip_id = uuid.uuid4()
            clip_storage_path = storage.upload_clip(
                file_path=clip_path,
                organization_id=str(video.organization_id),
                video_id=str(video.video_id),
                clip_id=str(clip_id),
            )

            # Extrai transcrição do clip baseado no timestamp
            clip_transcript = _extract_clip_transcript(
                transcript=transcript,
                start_time=start_time,
                end_time=end_time,
            )

            # Cria registro Clip no banco
            clip_objeto = Clip.objects.create(
                clip_id=clip_id,
                video=video,
                title=hook_title,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                storage_path=clip_storage_path,
                file_size=os.path.getsize(clip_path),
                transcript=clip_transcript,
            )

            generated_clips.append({
                "clip_id": str(clip_id),
                "title": hook_title,
                "duration": end_time - start_time,
            })

            # Limpa arquivo local
            if os.path.exists(clip_path):
                os.remove(clip_path)
            
            # Dispara task de scoring para gerar scores e thumbnail
            from .clip_scoring_task import clip_scoring_task
            clip_scoring_task.apply_async(
                args=[str(clip_id), str(video.video_id)],
                queue=f"video.process.{org.plan}",
            )

        # Atualiza vídeo
        video.last_successful_step = "clipping"
        video.status = "captioning"
        video.current_step = "captioning"
        video.save()
        
        # Atualiza job status
        update_job_status(str(video.video_id), "captioning", progress=85, current_step="captioning")

        # Dispara próxima task (captioning)
        from .caption_clips_task import caption_clips_task
        caption_clips_task.apply_async(
            args=[str(video.video_id)],
            queue=f"video.caption.{org.plan}",
        )

        return {
            "video_id": str(video.video_id),
            "status": "captioning",
            "clips_generated": len(generated_clips),
            "clips": generated_clips,
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "clipping"
        video.error_code = "CLIPPING_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _extract_clip_transcript(transcript: Transcript, start_time: float, end_time: float) -> str:
    """
    Extrai transcrição do clip baseado no timestamp.
    
    Args:
        transcript: Objeto Transcript
        start_time: Tempo inicial em segundos
        end_time: Tempo final em segundos
        
    Returns:
        Texto da transcrição do clip
    """
    segments = transcript.segments or []
    clip_text = []
    
    for segment in segments:
        seg_start = segment.get("start", 0)
        seg_end = segment.get("end", 0)
        seg_text = segment.get("text", "")
        
        # Se segmento está dentro do intervalo do clip
        if seg_start >= start_time and seg_end <= end_time:
            clip_text.append(seg_text)
        # Se segmento sobrepõe parcialmente
        elif seg_start < end_time and seg_end > start_time:
            clip_text.append(seg_text)
    
    return " ".join(clip_text).strip()


def _generate_clip_with_ffmpeg(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    ass_file: str = None,
) -> None:
    """
    Gera clip com FFmpeg.
    
    Aplica:
    - Corte nos timestamps
    - Legenda ASS queimada (se disponível)
    - Normalização de áudio
    - Codec H.264
    """
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 600))

    duration = end_time - start_time

    # Constrói comando FFmpeg
    cmd = [
        ffmpeg_path,
        "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(duration),
    ]

    # Adiciona filtro de legenda se disponível
    if ass_file and os.path.exists(ass_file):
        # Escapa o caminho para FFmpeg
        ass_path = ass_file.replace("\\", "/")
        cmd.extend([
            "-vf", f"ass={ass_path}",
        ])

    # Codec e áudio
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ])

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ffmpeg_timeout,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg falhou ao gerar clip: {e}")
    except subprocess.TimeoutExpired:
        raise Exception("Geração de clip excedeu o tempo limite")

    if not os.path.exists(output_path):
        raise Exception("Arquivo de clip não foi criado")
