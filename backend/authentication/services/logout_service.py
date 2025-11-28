from django.contrib.auth import logout
from django.http import HttpRequest


def logout_service(request: HttpRequest) -> None:
    logout(request)
