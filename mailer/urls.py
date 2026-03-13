from django.urls import path

from mailer import views

urlpatterns = [
    path("preferences/", views.email_preferences, name="email_preferences"),
]
