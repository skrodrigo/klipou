from django.urls import path

from .views.clips_list_create_view import clips_list_create


urlpatterns = [
    path("clips/", clips_list_create, name="clips-list-create"),
]
