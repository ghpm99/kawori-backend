from . import views
from django.urls import path

urlpatterns = [
    path("", views.get_all_view, name="earnings_get_all"),
    path("total/", views.get_total_view, name="earnings_get_total"),
]
