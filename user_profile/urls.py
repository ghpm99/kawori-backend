from django.urls import path

from . import views

urlpatterns = [
    path('', views.user_view, name='auth_user'),
    path("groups/", views.user_groups, name="user_groups"),
]
