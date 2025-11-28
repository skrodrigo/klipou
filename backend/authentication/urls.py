from django.urls import path

from .views.login_view import login_view
from .views.logout_view import logout_view
from .views.register_view import register_view
from .views.me_view import me_view

urlpatterns = [
    path("login/", login_view, name="auth-login"),
    path("logout/", logout_view, name="auth-logout"),
    path("register/", register_view, name="auth-register"),
    path("me/", me_view, name="auth-me"),
]
