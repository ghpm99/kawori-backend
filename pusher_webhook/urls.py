from django.urls import path
from . import views

urlpatterns = [
    path('webhook', views.pusher_webhook, name='pusher_webhook'),
    path('auth', views.pusher_auth, name='pusher_auth')
]
