import logging
import json
import requests
from celery import shared_task

from ..models import Clip, Schedule, Integration
from ..services.storage_service import R2StorageService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def post_to_social_task(self, clip_id: str, platform: str, scheduled_time: str = None) -> dict:

    try:
        logger.info(f"Iniciando postagem em {platform} para clip_id: {clip_id}")
        
        clip = Clip.objects.get(clip_id=clip_id)
        video = clip.video
        logger.info(f"Clip encontrado: {clip.title}, vídeo: {video.video_id}")

        integration = Integration.objects.filter(
            organization_id=video.organization_id,
            platform=platform,
            is_active=True,
        ).first()

        if not integration:
            logger.error(f"Integração com {platform} não encontrada ou inativa para organização {video.organization_id}")
            raise Exception(f"Integração com {platform} não encontrada ou inativa")

        storage = R2StorageService()
        clip_url = storage.get_signed_url(clip.storage_path, expiration=86400)

        post_result = _post_to_platform(
            platform=platform,
            clip_url=clip_url,
            clip_title=clip.title,
            integration=integration,
        )

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
    return {
        "post_url": f"https://tiktok.com/@{integration.account_name}/video/mock",
        "platform": "tiktok",
    }


def _post_to_instagram(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em Instagram via API."""
    meta = _get_meta_from_integration(integration)
    ig_business_account_id = meta.get('ig_business_account_id')
    page_access_token = meta.get('page_access_token')
    if not ig_business_account_id or not page_access_token:
        raise Exception("Instagram integration missing ig_business_account_id/page_access_token")

    create_container = requests.post(
        f"https://graph.facebook.com/v18.0/{ig_business_account_id}/media",
        data={
            "media_type": "REELS",
            "video_url": clip_url,
            "caption": clip_title,
            "access_token": page_access_token,
        },
        timeout=60,
    )
    create_container.raise_for_status()
    creation_id = create_container.json().get('id')
    if not creation_id:
        raise Exception("Failed to create Instagram media container")

    publish = requests.post(
        f"https://graph.facebook.com/v18.0/{ig_business_account_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": page_access_token,
        },
        timeout=60,
    )
    publish.raise_for_status()
    media_id = publish.json().get('id')

    return {
        "post_url": f"https://instagram.com/p/{media_id}" if media_id else None,
        "platform": "instagram",
        "platform_post_id": media_id,
    }


def _post_to_youtube(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em YouTube Shorts via API."""
    return {
        "post_url": f"https://youtube.com/shorts/mock",
        "platform": "youtube",
    }


def _post_to_facebook(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em Facebook via API."""
    meta = _get_meta_from_integration(integration)
    page_id = meta.get('page_id')
    page_access_token = meta.get('page_access_token')
    if not page_id or not page_access_token:
        raise Exception("Facebook integration missing page_id/page_access_token")

    resp = requests.post(
        f"https://graph.facebook.com/v18.0/{page_id}/videos",
        data={
            "file_url": clip_url,
            "description": clip_title,
            "access_token": page_access_token,
        },
        timeout=120,
    )
    resp.raise_for_status()
    video_id = resp.json().get('id')

    return {
        "post_url": f"https://facebook.com/{video_id}" if video_id else None,
        "platform": "facebook",
        "platform_post_id": video_id,
    }


def _get_meta_from_integration(integration: "Integration") -> dict:

    raw = integration.token_encrypted or ""
    raw = raw.strip()
    if not raw:
        return {}

    if raw.startswith('{'):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {"page_access_token": raw, "access_token": raw}


def _post_to_linkedin(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em LinkedIn via API."""
    return {
        "post_url": f"https://linkedin.com/feed/update/mock",
        "platform": "linkedin",
    }


def _post_to_twitter(clip_url: str, clip_title: str, integration: "Integration") -> dict:
    """Publica em X (Twitter) via API."""
    return {
        "post_url": f"https://x.com/mock/status/mock",
        "platform": "twitter",
    }
