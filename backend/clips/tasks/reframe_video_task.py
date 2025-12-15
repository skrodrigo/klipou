"""
Task para reenquadramento automático.
Etapa: Reframing
Disponível apenas em Pro e Business.
Detecta rosto/frame dominante e define crop automático.
"""

import os
import subprocess
from celery import shared_task
from django.conf import settings

from ..models import Video, Transcript


@shared_task(bind=True, max_retries=5)
def reframe_video_task(self, video_id: int) -> dict:
    """
    Reenquadramento automático de vídeo.
    
    Detecta rosto/frame dominante.
    Define crop automático para proporções desejadas (9:16, 1:1, 16:9).
    Aplica tracking simples para manter foco no rosto/elemento principal.
    
    Nota: Disponível apenas em Pro e Business.
    """
    try:
        video = Video.objects.get(id=video_id)
        video.status = "reframing"
        video.current_step = "reframing"
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

        # Arquivo normalizado
        input_path = os.path.join(output_dir, "video_normalized.mp4")

        if not os.path.exists(input_path):
            raise Exception("Arquivo de vídeo normalizado não encontrado")

        # Detecta rosto/frame dominante
        reframe_data = _detect_and_reframe(input_path, output_dir)

        # Armazena dados de reenquadramento na transcrição
        transcript.reframe_data = reframe_data
        transcript.save()

        # Atualiza vídeo
        video.last_successful_step = "reframing"
        video.save()

        return {
            "video_id": video_id,
            "status": "reframing",
            "face_detected": reframe_data.get("face_detected", False),
            "dominant_region": reframe_data.get("dominant_region"),
        }

    except Video.DoesNotExist:
        return {"error": "Video not found", "status": "failed"}
    except Exception as e:
        video.status = "failed"
        video.current_step = "reframing"
        video.error_code = "REFRAMING_ERROR"
        video.error_message = str(e)
        video.retry_count += 1
        video.save()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _detect_and_reframe(video_path: str, output_dir: str) -> dict:
    """
    Detecta rosto/frame dominante e define crop automático.
    
    Usa visão computacional clássica (não IA).
    Retorna dados de reenquadramento para cada proporção.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise Exception("OpenCV não está instalado. Adicione 'opencv-python' às dependências")

    # Abre vídeo
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception("Não foi possível abrir o vídeo")

    # Extrai alguns frames para análise
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Carrega detector de rosto (Haar Cascade)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    face_detected = False
    dominant_region = None
    face_regions = []

    # Analisa frames em intervalos
    sample_frames = min(10, frame_count // 30)  # Amostra 10 frames
    for i in range(sample_frames):
        frame_idx = int((i + 1) * frame_count / (sample_frames + 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            continue

        # Detecta rostos
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            face_detected = True
            # Pega maior rosto
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face
            face_regions.append((x, y, w, h))

    cap.release()

    # Calcula região dominante (média dos rostos detectados)
    if face_regions:
        avg_x = int(sum(f[0] for f in face_regions) / len(face_regions))
        avg_y = int(sum(f[1] for f in face_regions) / len(face_regions))
        avg_w = int(sum(f[2] for f in face_regions) / len(face_regions))
        avg_h = int(sum(f[3] for f in face_regions) / len(face_regions))

        dominant_region = {
            "x": avg_x,
            "y": avg_y,
            "width": avg_w,
            "height": avg_h,
            "center_x": avg_x + avg_w // 2,
            "center_y": avg_y + avg_h // 2,
        }

    # Define crops para cada proporção
    crops = _calculate_crops(width, height, dominant_region)

    return {
        "face_detected": face_detected,
        "dominant_region": dominant_region,
        "video_resolution": f"{width}x{height}",
        "crops": crops,
    }


def _calculate_crops(width: int, height: int, dominant_region: dict = None) -> dict:
    """
    Calcula crop para cada proporção desejada.
    
    Proporções: 9:16, 1:1, 16:9
    """
    crops = {}

    # Se há região dominante, centraliza crop nela
    center_x = dominant_region["center_x"] if dominant_region else width // 2
    center_y = dominant_region["center_y"] if dominant_region else height // 2

    # 9:16 (vertical, para TikTok/Reels)
    crop_9_16_width = min(int(height * 9 / 16), width)
    crop_9_16_height = height
    crop_9_16_x = max(0, min(center_x - crop_9_16_width // 2, width - crop_9_16_width))
    crop_9_16_y = 0
    crops["9:16"] = {
        "x": crop_9_16_x,
        "y": crop_9_16_y,
        "width": crop_9_16_width,
        "height": crop_9_16_height,
    }

    # 1:1 (quadrado)
    crop_1_1_size = min(width, height)
    crop_1_1_x = max(0, min(center_x - crop_1_1_size // 2, width - crop_1_1_size))
    crop_1_1_y = max(0, min(center_y - crop_1_1_size // 2, height - crop_1_1_size))
    crops["1:1"] = {
        "x": crop_1_1_x,
        "y": crop_1_1_y,
        "width": crop_1_1_size,
        "height": crop_1_1_size,
    }

    # 16:9 (horizontal, para YouTube)
    crop_16_9_width = width
    crop_16_9_height = min(int(width * 9 / 16), height)
    crop_16_9_x = 0
    crop_16_9_y = max(0, min(center_y - crop_16_9_height // 2, height - crop_16_9_height))
    crops["16:9"] = {
        "x": crop_16_9_x,
        "y": crop_16_9_y,
        "width": crop_16_9_width,
        "height": crop_16_9_height,
    }

    return crops
