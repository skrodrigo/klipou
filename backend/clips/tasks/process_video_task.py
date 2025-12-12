import os
import re
import subprocess
import base64
from celery import shared_task
from django.core.cache import cache
from django.conf import settings
from django.core.files import File
import requests

from ..models import Video, VideoClip


@shared_task(bind=True)
def process_video_task(self, video_id: int) -> dict:
    """Processa vídeo com Whisper + FFmpeg locais"""
    import time
    
    failed_stage = None
    api_url = f"http://localhost:8000/api/videos/{video_id}/status/"
    
    try:
        video = Video.objects.get(id=video_id)
        video.status = "processing"
        video.task_id = self.request.id
        video.save()

        output_dir = os.path.join(settings.MEDIA_ROOT, f"clips/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        duration, thumbnail_path = _extract_metadata_with_ffmpeg(video.file.path, output_dir)
        if thumbnail_path:
            with open(thumbnail_path, "rb") as f:
                thumbnail_data = f.read()
                video.thumbnail = f"data:image/jpeg;base64,{base64.b64encode(thumbnail_data).decode()}"
        video.duration = duration
        video.save()

        video_path = video.file.path
        output_dir = os.path.join(settings.MEDIA_ROOT, f"clips/{video_id}")
        os.makedirs(output_dir, exist_ok=True)

        failed_stage = "sending"
        requests.post(api_url, json={
            "status": "sending",
            "progress": 20,
        })
        time.sleep(2)  
        
        srt_file = _generate_srt_with_whisper(video_path, output_dir)
        raw_segments = _parse_srt_file(srt_file)
        candidate_clips = _build_clip_candidates(raw_segments)

        failed_stage = "creating"
        requests.post(api_url, json={
            "status": "creating",
            "progress": 50,
        })
        time.sleep(2) 
        
        clips_data = _generate_clips_with_ffmpeg(video_path, output_dir, candidate_clips)

        failed_stage = "hunting"
        requests.post(api_url, json={
            "status": "hunting",
            "progress": 75,
        })
        time.sleep(2)  
        
        for clip_info in clips_data:
            VideoClip.objects.create(
                video=video,
                title=clip_info["title"],
                start_time=clip_info["start_time"],
                end_time=clip_info["end_time"],
            )

        video.status = "completed"
        video.save()
        requests.post(api_url, json={
            "status": "completed",
            "progress": 100,
        })

        return {"video_id": video_id, "status": "completed"}

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        try:
            video = Video.objects.get(id=video_id)
            video.status = "failed"
            video.save()
        except Video.DoesNotExist:
            pass

        error_msg = str(e)
        if "Whisper" in error_msg or "segmentos" in error_msg:
            user_friendly_error = "Falha ao gerar transcrição. O áudio do vídeo pode estar inaudível ou corrompido."
        elif "ffmpeg" in error_msg.lower() or "áudio" in error_msg.lower():
            user_friendly_error = "Falha ao processar o áudio do vídeo. Verifique se o arquivo é válido."
        else:
            user_friendly_error = "Falha ao processar o vídeo. Por favor, verifique o arquivo e tente novamente."
        
        payload = {
            "status": "failed",
            "progress": 0,
            "error": user_friendly_error,
            "failed_stage": failed_stage
        }
        if api_url:
            requests.post(api_url, json=payload)

        return {"error": user_friendly_error, "status": "failed"}


def _generate_srt_with_whisper(video_path: str, output_dir: str) -> str:
    """Gera arquivo SRT local usando modelo Whisper."""
    try:
        import whisper
    except ImportError as exc:  # pragma: no cover - falha de dependência em runtime
        raise Exception(
            "Whisper não está instalado. Adicione 'openai-whisper' às dependências do backend."
        ) from exc

    os.makedirs(output_dir, exist_ok=True)

    audio_path = _extract_audio_with_ffmpeg(video_path, output_dir)

    model_name = getattr(settings, "WHISPER_MODEL", "base")
    device = getattr(settings, "WHISPER_DEVICE", "cpu")

    try:
        model = whisper.load_model(model_name, device=device)
        result = model.transcribe(audio_path)
    except Exception as exc:  
        raise Exception(f"Whisper falhou ao transcrever o vídeo: {exc}") from exc

    segments = result.get("segments") or []
    if not segments:
        raise Exception("Não foi possível gerar os segmentos de áudio")

    srt_file = os.path.join(output_dir, "transcript.srt")

    with open(srt_file, "w", encoding="utf-8") as f:
        index = 1
        for seg in segments:
            start = seg.get("start")
            end = seg.get("end")
            text = (seg.get("text") or "").strip()

            if text == "" or start is None or end is None:
                continue

            start_ts = _seconds_to_srt_time(float(start))
            end_ts = _seconds_to_srt_time(float(end))

            f.write(f"{index}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{text}\n\n")
            index += 1

    if not os.path.exists(srt_file):
        raise Exception("Falha ao gerar arquivo SRT com Whisper")

    return srt_file


def _extract_audio_with_ffmpeg(video_path: str, output_dir: str) -> str:
    """Extrai faixa de áudio do vídeo em WAV mono 16kHz para uso pelo Whisper."""
    audio_path = os.path.join(output_dir, "audio_for_whisper.wav")

    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    try:
        ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 600))
    except (TypeError, ValueError):
        ffmpeg_timeout = 600

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        audio_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ffmpeg_timeout,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise Exception("ffmpeg falhou ao extrair o áudio para Whisper") from exc

    if not os.path.exists(audio_path):
        raise Exception("Arquivo de áudio para Whisper não foi gerado")

    return audio_path


def _build_clip_candidates(
    segments: list,
    min_duration: float = 45.0,
    max_duration: float = 90.0,
    max_clips: int = 10,
) -> list:
    """Agrupa segmentos em candidatos de clipes e retorna os melhores pelo score.

    Heurística inspirada em:
    - frases completas
    - janelas de 45–90s
    - densidade semântica
    - intensidade emocional
    - palavras-chave fortes
    """

    if not segments:
        return []

    raw_candidates = []
    current = None

    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        text = (seg.get("title") or "").strip()

        if text == "" or end <= start:
            continue

        if current is None:
            current = {
                "start": start,
                "end": end,
                "text": text,
                "last_end": end,
            }
            continue

        proposed_start = current["start"]
        proposed_end = end
        duration = proposed_end - proposed_start
        gap = start - current["last_end"]

        if duration > max_duration:
            # Fecha candidato se já atingiu duração mínima
            if current["end"] - current["start"] >= min_duration:
                raw_candidates.append(current)

            # Começa novo candidato a partir deste segmento
            current = {
                "start": start,
                "end": end,
                "text": text,
                "last_end": end,
            }
            continue

        # Agrega ao candidato atual
        current["end"] = end
        current["last_end"] = end
        current["text"] = f"{current['text']} {text}"

        duration = current["end"] - current["start"]

        # Limites para fechar um candidato "bom":
        # - já passou do mínimo
        # - e temos um boundary forte (pausa grande ou término de frase)
        strong_boundary = gap >= 3.0 or text.endswith((".", "!", "?"))

        if duration >= min_duration and strong_boundary:
            raw_candidates.append(current)
            current = None

    # Último candidato pendente
    if current and current["end"] - current["start"] >= min_duration:
        raw_candidates.append(current)

    # Fallback: se nada atingiu a duração mínima, usa segmentos originais
    if not raw_candidates:
        for seg in segments:
            start = float(seg["start"])
            end = float(seg["end"])
            text = (seg.get("title") or "").strip()
            if text != "" and end > start:
                raw_candidates.append({"start": start, "end": end, "text": text})

    scored = []
    for cand in raw_candidates:
        start = float(cand["start"])
        end = float(cand["end"])
        text = cand.get("text") or ""
        score = _score_clip_candidate(text, start, end)
        scored.append({"start": start, "end": end, "title": text, "score": score})

    scored.sort(key=lambda c: c["score"], reverse=True)
    top = scored[:max_clips]

    return [
        {"start": c["start"], "end": c["end"], "title": c["title"][:100]}
        for c in top
    ]


def _score_clip_candidate(text: str, start: float, end: float) -> float:
    """Calcula um score heurístico para um candidato de clipe.

    Aproxima:
    - densidade semântica (palavras / segundo)
    - intensidade emocional (palavras emocionais, !, ?)
    - clareza narrativa (frase bem terminada)
    - palavras importantes (keywords)
    """

    duration = max(end - start, 1.0)
    cleaned = text.lower()
    words = re.findall(r"\w+", cleaned)
    n_words = len(words)

    # Densidade semântica
    density = n_words / duration

    # Palavras-chave fortes (mistura PT/EN para conteúdo híbrido)
    keyword_set = {
        "segredo",
        "segredos",
        "importante",
        "nunca",
        "sempre",
        "erro",
        "erros",
        "certo",
        "melhor",
        "pior",
        "dica",
        "dicas",
        "hack",
        "truque",
        "atenção",
        "alerta",
        "cuidado",
        "viral",
        "crescer",
        "vender",
        "vendas",
        "dinheiro",
        "resultado",
        "resultados",
        "história",
        "historia",
        "story",
    }

    emotional_words = {
        "incrível",
        "incrivel",
        "fantástico",
        "fantastico",
        "perfeito",
        "horrível",
        "horrivel",
        "maravilhoso",
        "tenso",
        "chocado",
        "chocante",
        "surpreendente",
        "impactante",
        "amo",
        "odiar",
    }

    keyword_hits = sum(1 for w in words if w in keyword_set)
    emotional_hits = sum(1 for w in words if w in emotional_words)

    exclam = text.count("!") + text.count("?")

    # Clareza narrativa básica: termina com pontuação forte
    clarity = 1.0 if text.strip().endswith((".", "!", "?")) else 0.0

    score = (
        density * 1.0
        + keyword_hits * 0.6
        + emotional_hits * 0.8
        + exclam * 0.3
        + clarity * 0.5
    )

    return score


def _generate_clips_with_ffmpeg(video_path: str, output_dir: str, clips_info: list) -> list:
    """Gera clipes de vídeo localmente usando ffmpeg, a partir dos timestamps do SRT."""
    clips_data = []

    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    try:
        ffmpeg_timeout = int(getattr(settings, "FFMPEG_TIMEOUT", 600))
    except (TypeError, ValueError):
        ffmpeg_timeout = 600

    for idx, clip_info in enumerate(clips_info):
        start_time = float(clip_info["start"])
        end_time = float(clip_info["end"])
        title = clip_info.get("title", f"Clip {idx + 1}")

        duration = end_time - start_time
        if duration <= 0:
            continue

        output_file = os.path.join(output_dir, f"clip_{idx + 1}.mp4")

        cmd = [
            ffmpeg_path,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-i",
            video_path,
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            output_file,
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=ffmpeg_timeout,
            )

            if os.path.exists(output_file):
                clips_data.append(
                    {
                        "title": title,
                        "start_time": start_time,
                        "end_time": end_time,
                        "file_path": output_file,
                    }
                )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Se ffmpeg não estiver instalado ou falhar no corte, apenas ignora o clipe atual
            continue

    if not clips_data:
        raise Exception("Nenhum clipe foi gerado pelo ffmpeg")

    return clips_data


def _seconds_to_srt_time(seconds: float) -> str:
    """Converte segundos (float) para formato SRT HH:MM:SS,mmm."""
    total_millis = int(round(seconds * 1000))
    hours, rem = divmod(total_millis, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _parse_srt_file(srt_file: str) -> list:
    """Parse SRT file e extrai timestamps"""
    if not os.path.exists(srt_file):
        raise Exception(f"SRT file not found: {srt_file}")

    clips = []
    with open(srt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    clip_index = 1
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            times = line.split("-->")
            start_seconds = _srt_time_to_seconds(times[0].strip())
            end_seconds = _srt_time_to_seconds(times[1].strip())

            title = f"Clip {clip_index}"
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.isdigit():
                    title = next_line[:100]

            clips.append({"start": start_seconds, "end": end_seconds, "title": title})
            clip_index += 1

        i += 1

    return clips


def _srt_time_to_seconds(time_str: str) -> float:
    """Converte tempo SRT (HH:MM:SS,mmm) para segundos"""
    time_str = time_str.replace(",", ".")
    parts = time_str.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _extract_metadata_with_ffmpeg(video_path: str, output_dir: str) -> tuple[float | None, str | None]:
    """Extrai duração e thumbnail de um vídeo usando ffmpeg/ffprobe."""
    ffmpeg_path = getattr(settings, "FFMPEG_PATH", "ffmpeg")
    ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")
    thumbnail_path = os.path.join(output_dir, "thumbnail.jpg")
    duration = None

    try:
        # Extrair duração
        cmd_duration = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())

        # Extrair thumbnail (em 10% do vídeo)
        thumbnail_time = duration * 0.1
        cmd_thumbnail = [
            ffmpeg_path,
            "-y",
            "-ss", str(thumbnail_time),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumbnail_path
        ]
        subprocess.run(cmd_thumbnail, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None, None

    return duration, thumbnail_path if os.path.exists(thumbnail_path) else None

