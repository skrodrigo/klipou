"""
Views para gerenciamento de integrações com redes sociais.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
import uuid

from ..models import Integration, Organization


@api_view(["GET"])
def list_integrations(request, organization_id):
    """
    Lista todas as integrações de uma organização.
    
    Query params:
    - platform: filtering por plataforma
    """
    try:
        platform_filter = request.query_params.get("platform")
        
        # Valida permissão
        user_org_id = request.query_params.get("user_organization_id")
        if user_org_id != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = Integration.objects.filter(organization_id=organization_id)

        if platform_filter:
            query = query.filter(platform=platform_filter)

        integrations = query.order_by("-created_at")

        return Response(
            {
                "integrations": [
                    {
                        "integration_id": str(integration.integration_id),
                        "platform": integration.platform,
                        "account_name": integration.account_name,
                        "is_active": integration.is_active,
                        "created_at": integration.created_at.isoformat(),
                        "last_posted_at": integration.last_posted_at.isoformat() if integration.last_posted_at else None,
                    }
                    for integration in integrations
                ],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def connect_integration(request):
    """
    Inicia fluxo OAuth para conectar rede social.
    
    Body:
    {
        "platform": "tiktok|instagram|youtube|facebook|linkedin|twitter",
        "organization_id": "uuid"
    }
    
    Response:
    {
        "oauth_url": "https://...",
        "state": "random_state_token"
    }
    """
    try:
        platform = request.data.get("platform")
        organization_id = request.data.get("organization_id")

        # Valida plataforma
        valid_platforms = ["tiktok", "instagram", "youtube", "facebook", "linkedin", "twitter"]
        if platform not in valid_platforms:
            return Response(
                {"error": f"Invalid platform. Valid: {', '.join(valid_platforms)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida organização
        org = Organization.objects.get(organization_id=organization_id)

        # Gera state token para CSRF protection
        state = str(uuid.uuid4())

        # Armazena state em cache (TTL 10 minutos)
        from django.core.cache import cache
        cache.set(f"oauth_state:{state}", organization_id, 600)

        # Gera OAuth URL baseado na plataforma
        oauth_url = _get_oauth_url(platform, state)

        return Response(
            {
                "oauth_url": oauth_url,
                "state": state,
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def oauth_callback(request):
    """
    Callback OAuth após usuário autorizar.
    
    Query params:
    - code: authorization code
    - state: state token
    - platform: plataforma
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        platform = request.query_params.get("platform")
        organization_id = request.data.get("organization_id")

        if not code or not state or not platform:
            return Response(
                {"error": "Missing required parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida state token
        from django.core.cache import cache
        cached_org_id = cache.get(f"oauth_state:{state}")

        if not cached_org_id or cached_org_id != organization_id:
            return Response(
                {"error": "Invalid state token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Troca code por token
        token_response = _exchange_code_for_token(platform, code)

        if not token_response.get("access_token"):
            return Response(
                {"error": "Failed to obtain access token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obtém informações da conta
        account_info = _get_account_info(platform, token_response["access_token"])

        # Cria ou atualiza integração
        integration, created = Integration.objects.update_or_create(
            organization_id=organization_id,
            platform=platform,
            account_name=account_info.get("account_name"),
            defaults={
                "token_encrypted": token_response["access_token"],  # TODO: Criptografar
                "is_active": True,
            },
        )

        # Remove state token do cache
        cache.delete(f"oauth_state:{state}")

        return Response(
            {
                "integration_id": str(integration.integration_id),
                "platform": platform,
                "account_name": integration.account_name,
                "is_active": True,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def disconnect_integration(request, integration_id):
    """
    Desconecta uma integração social.
    
    Body:
    {
        "organization_id": "uuid"
    }
    """
    try:
        integration = Integration.objects.get(integration_id=integration_id)
        organization_id = request.data.get("organization_id")

        # Valida permissão
        if str(integration.organization_id) != organization_id:
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Revoga token (implementação específica por plataforma)
        _revoke_token(integration.platform, integration.token_encrypted)

        # Marca como inativo
        integration.is_active = False
        integration.save()

        return Response(
            {
                "integration_id": str(integration.integration_id),
                "status": "disconnected",
            },
            status=status.HTTP_200_OK,
        )

    except Integration.DoesNotExist:
        return Response(
            {"error": "Integration not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


# Funções auxiliares (implementação específica por plataforma)

def _get_oauth_url(platform: str, state: str) -> str:
    """Gera URL OAuth para a plataforma."""
    from django.conf import settings

    oauth_urls = {
        "tiktok": f"https://www.tiktok.com/oauth/authorize?client_id={settings.TIKTOK_CLIENT_ID}&redirect_uri={settings.TIKTOK_REDIRECT_URI}&response_type=code&scope=user.info.basic&state={state}",
        "instagram": f"https://api.instagram.com/oauth/authorize?client_id={settings.INSTAGRAM_CLIENT_ID}&redirect_uri={settings.INSTAGRAM_REDIRECT_URI}&scope=user_profile,user_media&response_type=code&state={state}",
        "youtube": f"https://accounts.google.com/o/oauth2/v2/auth?client_id={settings.YOUTUBE_CLIENT_ID}&redirect_uri={settings.YOUTUBE_REDIRECT_URI}&response_type=code&scope=https://www.googleapis.com/auth/youtube.upload&state={state}",
        "facebook": f"https://www.facebook.com/v18.0/dialog/oauth?client_id={settings.FACEBOOK_CLIENT_ID}&redirect_uri={settings.FACEBOOK_REDIRECT_URI}&scope=pages_manage_posts&state={state}",
        "linkedin": f"https://www.linkedin.com/oauth/v2/authorization?client_id={settings.LINKEDIN_CLIENT_ID}&redirect_uri={settings.LINKEDIN_REDIRECT_URI}&response_type=code&scope=w_member_social&state={state}",
        "twitter": f"https://twitter.com/i/oauth2/authorize?client_id={settings.TWITTER_CLIENT_ID}&redirect_uri={settings.TWITTER_REDIRECT_URI}&response_type=code&scope=tweet.write%20tweet.read%20users.read&state={state}",
    }

    return oauth_urls.get(platform, "")


def _exchange_code_for_token(platform: str, code: str) -> dict:
    """Troca authorization code por access token."""
    # TODO: Implementar para cada plataforma
    return {"access_token": code}  # Placeholder


def _get_account_info(platform: str, access_token: str) -> dict:
    """Obtém informações da conta."""
    # TODO: Implementar para cada plataforma
    return {"account_name": "account"}  # Placeholder


def _revoke_token(platform: str, token: str) -> None:
    """Revoga access token."""
    # TODO: Implementar para cada plataforma
    pass
