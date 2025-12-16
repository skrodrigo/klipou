import logging
from celery import shared_task

from ..models import Clip, Schedule, Integration
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def post_to_social_task(self, clip_id: str, platform: str, scheduled_time: str = None) -> dict:
    """
    Publica clip em rede social.
    
    Suporta:
    - TikTok
    - Instagram
    - Facebook
    - YouTube Shorts
    - LinkedIn
    - X (Twitter)
    """
    try:
        logger.info(f"Iniciando postagem em {platform} para clip_id: {clip_id}")
        
        clip = Clip.objects.get(clip_id=clip_id)
        video = clip.video
        logger.info(f"Clip encontrado: {clip.title}, vídeo: {video.video_id}")

        # Obtém integração da organização
        integration = Integration.objects.filter(
            organization_id=video.organization_id,
            platform=platform,
            is_active=True,
        ).first()

        if not integration:
            logger.error(f"Integração com {platform} não encontrada ou inativa para organização {video.organization_id}")
            raise Exception(f"Integração com {platform} não encontrada ou inativa")

        # Gera URL assinada para o clip
        storage = R2StorageService()
        clip_url = storage.get_signed_url(clip.storage_path, expiration=86400)

        # Publica no platform específico
        post_result = _post_to_platform(
            platform=platform,
            clip_url=clip_url,
            clip_title=clip.title,
            integration=integration,
        )

        # Cria registro de Schedule
        schedule = Schedule.objects.create(
            clip=clip,
            user_id=video.user_id,
            platform=platform,
            scheduled_time=scheduled_time,
            status="posted",
            post_url=post_result.get("post_url"),
        )

        return {
            "clip_id": clip_id,
            "platform": platform,
            "status": "posted",
            "post_url": post_result.get("post_url"),
            "schedule_id": str(schedule.schedule_id),
        }

    except Clip.DoesNotExist:
        logger.error(f"Clip não encontrado: {clip_id}")
        return {"error": "Clip not found", "status": "failed"}
    except Exception as e:
        logger.error(f"Erro ao postar em {platform} para clip {clip_id}: {e}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {"error": str(e), "status": "failed"}


def _post_to_platform(
    platform: str,
    clip_url: str,
    clip_title: str,
    integration: "Integration",
) -> dict:
    """
    Publica clip na plataforma específica.
    
    Implementação depende da API de cada rede social.
    """
    if platform == "tiktok":
        return _post_to_tiktok(clip_url, clip_title, integration)
    elif platform == "instagram":
        return _post_to_instagram(clip_url, clip_title, integration)
    elif platform == "youtube":
        return _post_to_youtube(clip_url, clip_title, integration)
    elif platform == "facebook":
        return _post_to_facebook(clip_url, clip_title, integration)
    elif platform == "linkedin":
        return _post_to_linkedin(clip_url, clip_title, integration)
    elif platform == "twitter":
        return _post_to_twitter(clip_url, clip_title, integration)
    else:
        raise Exception(f"Plataforma não suportada: {platform}")


def _post_to_tiktok(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em TikTok via API."""
    # Implementação depende de TikTok API
    # Por enquanto, retorna mock
    return {
        "post_url": f"https://tiktok.com/@{integration.account_name}/video/mock",
        "platform": "tiktok",
    }


def _post_to_instagram(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em Instagram via API."""
    # Implementação depende de Instagram Graph API
    return {
        "post_url": f"https://instagram.com/p/mock",
        "platform": "instagram",
    }


def _post_to_youtube(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em YouTube Shorts via API."""
    # Implementação depende de YouTube API
    return {
        "post_url": f"https://youtube.com/shorts/mock",
        "platform": "youtube",
    }


def _post_to_facebook(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em Facebook via API."""
    # Implementação depende de Facebook Graph API
    return {
        "post_url": f"https://facebook.com/mock",
        "platform": "facebook",
    }


def _post_to_linkedin(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em LinkedIn via API."""
    # Implementação depende de LinkedIn API
    return {
        "post_url": f"https://linkedin.com/feed/update/mock",
        "platform": "linkedin",
    }


def _post_to_twitter(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em X (Twitter) via API."""
    # Implementação depende de X API v2
    return {
        "post_url": f"https://x.com/mock/status/mock",
        "platform": "twitter",
    }
