from django.urls import path

from .views.login_view import login_view
from .views.logout_view import logout_view
from .views.register_view import register_view
from .views.me_view import me_view
from .views.update_profile_view import update_profile_view
from .views.organizations_view import organizations_view, switch_organization_view
from .views.oauth_callback_view import (
    oauth_authorize,
    oauth_callback,
    list_social_accounts,
    disconnect_social_account,
    refresh_social_token,
)

urlpatterns = [
    path("login/", login_view, name="auth-login"),
    path("logout/", logout_view, name="auth-logout"),
    path("register/", register_view, name="auth-register"),
    path("me/", me_view, name="auth-me"),
    path("me/update/", update_profile_view, name="update_profile"),
    path("organizations/", organizations_view, name="organizations"),
    path("organizations/switch/", switch_organization_view, name="switch_organization"),
    
    # OAuth endpoints
    path("oauth/authorize/<str:platform>/", oauth_authorize, name="oauth-authorize"),
    path("oauth/callback/<str:platform>/", oauth_callback, name="oauth-callback"),
    path("social-accounts/", list_social_accounts, name="list-social-accounts"),
    path("social-accounts/<str:platform>/disconnect/", disconnect_social_account, name="disconnect-social-account"),
    path("social-accounts/<str:platform>/refresh-token/", refresh_social_token, name="refresh-social-token"),
]
