"""
Validadores para mídia, URLs externas e quotas.
"""

import os
import subprocess
from django.conf import settings


class MediaValidator:
    """Valida vídeos conforme limites de plano."""

    # Limites por plano (em minutos)
    DURATION_LIMITS = {
        "starter": 30,  # 30 minutos
        "pro": 60,  # 60 minutos
        "business": 120,  # 120 minutos
    }

    # Limites de tamanho por plano (em MB)
    SIZE_LIMITS = {
        "starter": 500,  # 500 MB
        "pro": 2000,  # 2 GB
        "business": 5000,  # 5 GB
    }

    # Formatos permitidos
    ALLOWED_FORMATS = ["mp4", "webm", "mov", "mkv"]

    # Codecs de vídeo permitidos
    ALLOWED_VIDEO_CODECS = ["h264", "h265", "vp9", "vp8"]

    # Codecs de áudio obrigatórios
    REQUIRED_AUDIO_CODECS = ["aac", "mp3", "opus", "flac"]

    # Resolução mínima
    MIN_RESOLUTION = 480  # 480p

    @classmethod
    def validate_file(cls, file, plan: str = "starter") -> dict:
        """
        Valida arquivo de vídeo.

        Args:
            file: Arquivo Django
            plan: Plano do usuário (starter, pro, business)

        Returns:
            Dict com resultado da validação: {valid: bool, errors: list, metadata: dict}

        Raises:
            Exception: Se arquivo não puder ser validado
        """
        errors = []
        metadata = {}

        # 1. Valida tamanho
        file_size_mb = file.size / (1024 * 1024)
        size_limit = cls.SIZE_LIMITS.get(plan, 500)

        if file_size_mb > size_limit:
            errors.append(f"Arquivo muito grande ({file_size_mb:.1f}MB). Limite: {size_limit}MB")

        # 2. Valida extensão
        filename = file.name.lower()
        ext = filename.split(".")[-1] if "." in filename else ""

        if ext not in cls.ALLOWED_FORMATS:
            errors.append(f"Formato não suportado (.{ext}). Permitidos: {', '.join(cls.ALLOWED_FORMATS)}")

        # 3. Extrai metadados com ffprobe
        try:
            metadata = cls._get_video_metadata(file)
        except Exception as e:
            errors.append(f"Erro ao analisar vídeo: {str(e)}")
            return {"valid": False, "errors": errors, "metadata": {}}

        # 4. Valida duração
        duration = metadata.get("duration", 0)
        duration_limit = cls.DURATION_LIMITS.get(plan, 30)

        if duration > duration_limit * 60:  # Converte para segundos
            errors.append(f"Vídeo muito longo ({duration / 60:.1f}min). Limite: {duration_limit}min")

        if duration < 1:
            errors.append("Vídeo muito curto (mínimo 1 segundo)")

        # 5. Valida resolução
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)

        if width < cls.MIN_RESOLUTION or height < cls.MIN_RESOLUTION:
            errors.append(f"Resolução muito baixa ({width}x{height}). Mínimo: {cls.MIN_RESOLUTION}p")

        # 6. Valida codec de vídeo
        video_codec = metadata.get("video_codec", "").lower()
        if video_codec and video_codec not in cls.ALLOWED_VIDEO_CODECS:
            errors.append(f"Codec de vídeo não suportado ({video_codec})")

        # 7. Valida codec de áudio
        audio_codec = metadata.get("audio_codec", "").lower()
        if not audio_codec:
            errors.append("Vídeo não possui faixa de áudio")
        elif audio_codec not in cls.REQUIRED_AUDIO_CODECS:
            errors.append(f"Codec de áudio não suportado ({audio_codec})")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "metadata": metadata,
        }

    @classmethod
    def _get_video_metadata(cls, file) -> dict:
        """Extrai metadados do vídeo usando ffprobe."""
        ffprobe_path = getattr(settings, "FFMPEG_PATH", "ffmpeg").replace("ffmpeg", "ffprobe")

        # Salva arquivo temporário
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            # Extrai duração
            cmd_duration = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                tmp_path,
            ]
            result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())

            # Extrai resolução e codecs
            cmd_streams = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name",
                "-of", "csv=p=0",
                tmp_path,
            ]
            result = subprocess.run(cmd_streams, capture_output=True, text=True, check=True)
            parts = result.stdout.strip().split(",")
            width = int(parts[0]) if len(parts) > 0 else 0
            height = int(parts[1]) if len(parts) > 1 else 0
            video_codec = parts[2] if len(parts) > 2 else ""

            # Extrai codec de áudio
            cmd_audio = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                tmp_path,
            ]
            result = subprocess.run(cmd_audio, capture_output=True, text=True, check=True)
            audio_codec = result.stdout.strip()

            return {
                "duration": duration,
                "width": width,
                "height": height,
                "video_codec": video_codec,
                "audio_codec": audio_codec,
            }

        finally:
            # Limpa arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class URLValidator:
    """Valida URLs externas contra SSRF e domínios permitidos."""

    ALLOWED_DOMAINS = {
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "vm.tiktok.com",
        "instagram.com",
        "instagr.am",
    }

    @classmethod
    def validate_url(cls, url: str) -> dict:
        """
        Valida URL externa.

        Args:
            url: URL a validar

        Returns:
            Dict com resultado: {valid: bool, error: str or None}
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. se presente
            if domain.startswith("www."):
                domain = domain[4:]

            # Valida domínio
            if domain not in cls.ALLOWED_DOMAINS:
                return {
                    "valid": False,
                    "error": f"Domínio não permitido: {domain}. Permitidos: {', '.join(cls.ALLOWED_DOMAINS)}",
                }

            return {"valid": True, "error": None}

        except Exception as e:
            return {"valid": False, "error": f"URL inválida: {str(e)}"}
