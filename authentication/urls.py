from django.urls import path
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from kawori.decorators import add_cors_react_dev, move_cookie_token_to_header

from . import views

urlpatterns = [
    path("token/", views.obtain_token_pair, name="da_token_obtain_pair"),
    path("token/verify/", views.verify_token, name="da_token_verify"),
    path(
        "token/refresh/",
        add_cors_react_dev(move_cookie_token_to_header(TokenRefreshView.as_view())),
        name="da_token_refresh",
    ),
    path("signup", views.signup_view, name="auth_signup"),

]
