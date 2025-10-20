from django.urls import path

from . import views

urlpatterns = [
    path("new-users/", views.get_new_users, name="analytics_new_users"),
]
