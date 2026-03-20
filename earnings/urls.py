from django.urls import path

from . import views

urlpatterns = [
    path("", views.get_all_view, name="earnings_get_all"),
]
