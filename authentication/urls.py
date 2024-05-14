from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    # TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from kawori.decorators import add_cors_react_dev

from . import views

urlpatterns = [
    path("token/", views.obtain_token_pair, name="da_token_obtain_pair"),
    path(
        "token/verify/",
        csrf_exempt(add_cors_react_dev(TokenVerifyView.as_view())),
        name="da_token_verify",
    ),
    path(
        "token/refresh/",
        csrf_exempt(add_cors_react_dev(TokenRefreshView.as_view())),
        name="da_token_refresh",
    ),
    path("user", views.user_view, name="auth_user"),
    path("signup", views.signup_view, name="auth_signup"),
]
