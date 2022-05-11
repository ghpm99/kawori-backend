from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login_view, name='auth_login'),
    path('user', views.user_view, name='auth_user'),
]
