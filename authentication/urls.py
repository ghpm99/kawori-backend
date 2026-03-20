from django.urls import path

from . import views

urlpatterns = [
    path("token/", views.obtain_token_pair, name="da_token_obtain_pair"),
    path("token/verify/", views.verify_token, name="da_token_verify"),
    path("token/refresh/", views.refresh_token, name="da_token_refresh"),
    path("signup", views.signup_view, name="auth_signup"),
    path("signout", views.signout_view, name="auth_signout"),
    path("csrf/", views.obtain_csrf_cookie, name="obtain_csrf_cookie"),
    path(
        "password-reset/request/",
        views.request_password_reset,
        name="auth_password_reset_request",
    ),
    path(
        "password-reset/validate/",
        views.validate_reset_token,
        name="auth_password_reset_validate",
    ),
    path(
        "password-reset/confirm/",
        views.confirm_password_reset,
        name="auth_password_reset_confirm",
    ),
    path("email/verify/", views.verify_email, name="auth_email_verify"),
    path(
        "email/resend-verification/",
        views.resend_verification_email,
        name="auth_email_resend_verification",
    ),
    path("social/providers/", views.social_providers, name="auth_social_providers"),
    path(
        "social/<str:provider>/authorize/",
        views.social_authorize,
        name="auth_social_authorize",
    ),
    path(
        "social/<str:provider>/callback/",
        views.social_callback,
        name="auth_social_callback",
    ),
    path(
        "social/accounts/", views.social_accounts_list, name="auth_social_accounts_list"
    ),
    path(
        "social/accounts/<str:provider>/unlink/",
        views.social_account_unlink,
        name="auth_social_account_unlink",
    ),
]
