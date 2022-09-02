from django.urls import path
from . import views

urlpatterns = [
    path('signin', views.signin_view, name='auth_signin'),
    path('user', views.user_view, name='auth_user'),
    path('signup', views.signup_view, name='auth_signup'),
]
