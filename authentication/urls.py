from django.urls import path
from . import views

urlpatterns = [
    path("token/", views.obtain_token_pair, name="da_token_obtain_pair"),
    path("token/verify/", views.verify_token, name="da_token_verify"),
    path("token/refresh/", views.refresh_token, name="da_token_refresh"),
    path("signup", views.signup_view, name="auth_signup"),
    path("signout", views.signout_view, name="auth_signout"),
    path("csrf/", views.obtain_csrf_cookie, name="obtain_csrf_cookie"),
]
