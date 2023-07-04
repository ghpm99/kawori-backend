from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('signin', TokenObtainPairView.as_view(), name='auth_signin'),
    path('refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('user', views.user_view, name='auth_user'),
    path('signup', views.signup_view, name='auth_signup'),
]
