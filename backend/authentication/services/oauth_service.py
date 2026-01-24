import requests
import json
from abc import ABC, abstractmethod
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from authentication.models import SocialAccount


class OAuthProvider(ABC):
    """Base class for OAuth providers"""
    
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
    
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL"""
        pass
    
    @abstractmethod
    def exchange_code_for_token(self, code: str) -> dict:
        """Exchange authorization code for access token"""
        pass
    
    @abstractmethod
    def get_user_info(self, access_token: str) -> dict:
        """Get user info from provider"""
        pass
    
    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh access token"""
        pass


class TikTokOAuth(OAuthProvider):
    """TikTok OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.TIKTOK_CLIENT_ID
        self.client_secret = settings.TIKTOK_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/tiktok"
        self.auth_url = "https://www.tiktok.com/v1/oauth/authorize"
        self.token_url = "https://open.tiktokapis.com/v1/oauth/token"
        self.user_info_url = "https://open.tiktokapis.com/v1/user/info"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_key": self.client_id,
            "response_type": "code",
            "scope": "user.info.basic,video.list,video.publish",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{self.auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        data = {
            "client_key": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        response = requests.post(self.token_url, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_user_info(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"fields": "open_id,union_id,display_name,avatar_url"}
        response = requests.get(self.user_info_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_key": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = requests.post(self.token_url, json=data)
        response.raise_for_status()
        return response.json()


class InstagramOAuth(OAuthProvider):
    """Instagram OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.INSTAGRAM_CLIENT_ID
        self.client_secret = settings.INSTAGRAM_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/instagram"
        self.auth_url = "https://api.instagram.com/oauth/authorize"
        self.token_url = "https://graph.instagram.com/v18.0/access_token"
        self.user_info_url = "https://graph.instagram.com/v18.0/me"
    
    def get_authorization_url(self, state: str) -> str:
        raise NotImplementedError(
            "Instagram publishing is not supported via Instagram Basic Display OAuth. "
            "Use Facebook Login (platform='facebook') with Instagram Graph permissions instead."
        )
    
    def exchange_code_for_token(self, code: str) -> dict:
        raise NotImplementedError(
            "Instagram publishing is not supported via Instagram Basic Display OAuth. "
            "Use Facebook Login (platform='facebook') with Instagram Graph permissions instead."
        )
    
    def get_user_info(self, access_token: str) -> dict:
        raise NotImplementedError(
            "Instagram publishing is not supported via Instagram Basic Display OAuth. "
            "Use Facebook Login (platform='facebook') with Instagram Graph permissions instead."
        )
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        raise NotImplementedError(
            "Instagram publishing is not supported via Instagram Basic Display OAuth. "
            "Use Facebook Login (platform='facebook') with Instagram Graph permissions instead."
        )


class YouTubeOAuth(OAuthProvider):
    """YouTube OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/youtube"
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.user_info_url = "https://www.googleapis.com/youtube/v3/channels"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        response = requests.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()
    
    def get_user_info(self, access_token: str) -> dict:
        params = {
            "part": "snippet",
            "mine": "true",
            "access_token": access_token,
        }
        response = requests.get(self.user_info_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('items'):
            return data['items'][0]
        return data
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = requests.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()


class FacebookOAuth(OAuthProvider):
    """Facebook OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.FACEBOOK_CLIENT_ID
        self.client_secret = settings.FACEBOOK_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/facebook"
        self.auth_url = "https://www.facebook.com/v18.0/dialog/oauth"
        self.token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        self.user_info_url = "https://graph.facebook.com/v18.0/me"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,pages_manage_posts",
            "state": state,
            "response_type": "code",
        }
        return f"{self.auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        response = requests.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()
    
    def get_user_info(self, access_token: str) -> dict:
        params = {
            "fields": "id,name,picture",
            "access_token": access_token,
        }
        response = requests.get(self.user_info_url, params=params)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        # Facebook doesn't support refresh tokens for long-lived tokens
        # Return the same token
        return {"access_token": refresh_token}


class LinkedInOAuth(OAuthProvider):
    """LinkedIn OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/linkedin"
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.user_info_url = "https://api.linkedin.com/v2/me"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email w_member_social",
            "state": state,
        }
        return f"{self.auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = requests.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()
    
    def get_user_info(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(self.user_info_url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = requests.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()


class TwitterOAuth(OAuthProvider):
    """Twitter/X OAuth implementation"""
    
    def __init__(self):
        super().__init__()
        self.client_id = settings.TWITTER_CLIENT_ID
        self.client_secret = settings.TWITTER_CLIENT_SECRET
        self.redirect_uri = f"{settings.BACKEND_URL}/api/auth/callback/twitter"
        self.auth_url = "https://twitter.com/i/oauth2/authorize"
        self.token_url = "https://api.twitter.com/2/oauth2/token"
        self.user_info_url = "https://api.twitter.com/2/users/me"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "tweet.read tweet.write users.read",
            "state": state,
            "code_challenge": "challenge",
            "code_challenge_method": "plain",
        }
        return f"{self.auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code_verifier": "challenge",
        }
        auth = (self.client_id, self.client_secret)
        response = requests.post(self.token_url, data=data, auth=auth)
        response.raise_for_status()
        return response.json()
    
    def get_user_info(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user.fields": "id,name,username,profile_image_url"}
        response = requests.get(self.user_info_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        auth = (self.client_id, self.client_secret)
        response = requests.post(self.token_url, data=data, auth=auth)
        response.raise_for_status()
        return response.json()


class OAuthManager:
    """Manager for OAuth operations"""
    
    PROVIDERS = {
        'tiktok': TikTokOAuth,
        'instagram': InstagramOAuth,
        'youtube': YouTubeOAuth,
        'facebook': FacebookOAuth,
        'linkedin': LinkedInOAuth,
        'twitter': TwitterOAuth,
    }
    
    @staticmethod
    def get_provider(platform: str) -> OAuthProvider:
        """Get OAuth provider instance"""
        provider_class = OAuthManager.PROVIDERS.get(platform.lower())
        if not provider_class:
            raise ValueError(f"Unsupported platform: {platform}")
        return provider_class()
    
    @staticmethod
    def handle_oauth_callback(user, platform: str, code: str, state: str) -> SocialAccount:
        """Handle OAuth callback and create/update SocialAccount"""
        provider = OAuthManager.get_provider(platform)
        
        # Exchange code for token
        token_data = provider.exchange_code_for_token(code)
        
        # Get user info
        user_info = provider.get_user_info(token_data['access_token'])
        
        # Extract user data
        platform_user_id = user_info.get('id') or user_info.get('open_id')
        platform_username = user_info.get('username') or user_info.get('display_name')
        platform_display_name = user_info.get('name') or user_info.get('display_name')
        platform_profile_picture = user_info.get('profile_image_url') or user_info.get('avatar_url')
        
        # Calculate token expiration
        token_expires_at = None
        if 'expires_in' in token_data:
            token_expires_at = timezone.now() + timedelta(seconds=token_data['expires_in'])
        
        # Create or update SocialAccount
        social_account, created = SocialAccount.objects.update_or_create(
            user=user,
            platform=platform,
            platform_user_id=platform_user_id,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'token_expires_at': token_expires_at,
                'platform_username': platform_username,
                'platform_display_name': platform_display_name,
                'platform_profile_picture': platform_profile_picture,
                'is_connected': True,
            }
        )
        
        return social_account
    
    @staticmethod
    def disconnect_account(social_account: SocialAccount):
        """Disconnect a social account"""
        social_account.is_connected = False
        social_account.save()
