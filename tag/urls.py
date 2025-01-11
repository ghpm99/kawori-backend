from django.urls import path
from . import views

urlpatterns = [
    path("", views.get_all_tag_view, name="financial_get_all_tags"),
    path("new", views.include_new_tag_view, name="financial_include_tag"),
]
