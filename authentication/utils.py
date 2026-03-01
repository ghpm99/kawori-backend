import threading
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.template.loader import render_to_string
from rest_framework_simplejwt.tokens import RefreshToken


def get_token(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def register_groups(user: User) -> None:
    user_group = Group.objects.filter(name="user").first()
    if user_group is not None:
        user_group.user_set.add(user)

    black_desert_group = Group.objects.filter(name="blackdesert").first()
    if black_desert_group is not None:
        black_desert_group.user_set.add(user)

    financial_group = Group.objects.filter(name="financial").first()
    if financial_group is not None:
        financial_group.user_set.add(user)


def get_client_ip(request) -> str:
    """Extracts the real client IP, supporting reverse proxies via X-Forwarded-For."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _send_password_reset_email(user: User, raw_token: str) -> None:
    """Builds and sends the password reset email via SMTP. Runs in a background thread."""
    from authentication.models import UserToken

    try:
        reset_url = f"{settings.BASE_URL_FRONTEND}/reset-password?token={raw_token}"

        html_content = render_to_string(
            "password_reset_email.html",
            {
                "user": user,
                "token": raw_token,
                "reset_url": reset_url,
                "expiry_minutes": UserToken.EXPIRY_CONFIG[UserToken.TOKEN_TYPE_PASSWORD_RESET],
            },
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Redefinição de senha - Kawori"
        msg["From"] = settings.EMAIL_HOST_USER
        msg["To"] = user.email
        msg.attach(MIMEText(html_content, "html"))

        with SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print(f"[password_reset] Erro ao enviar email para {user.email}: {e}")


def send_password_reset_email_async(user: User, raw_token: str) -> None:
    """Dispatches the password reset email in a daemon thread."""
    thread = threading.Thread(
        target=_send_password_reset_email,
        args=(user, raw_token),
        daemon=True,
    )
    thread.start()


def _send_verification_email(user: User, raw_token: str) -> None:
    """Builds and sends the email verification email via SMTP. Runs in a background thread."""
    from authentication.models import UserToken

    try:
        verify_url = f"{settings.BASE_URL_FRONTEND}/verify-email?token={raw_token}"

        html_content = render_to_string(
            "email_verification.html",
            {
                "user": user,
                "verify_url": verify_url,
                "expiry_hours": UserToken.EXPIRY_CONFIG[UserToken.TOKEN_TYPE_EMAIL_VERIFICATION] // 60,
            },
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Bem-vindo ao Kawori - Verifique seu email"
        msg["From"] = settings.EMAIL_HOST_USER
        msg["To"] = user.email
        msg.attach(MIMEText(html_content, "html"))

        with SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print(f"[email_verification] Erro ao enviar email para {user.email}: {e}")


def send_verification_email_async(user: User, raw_token: str) -> None:
    """Dispatches the verification email in a daemon thread."""
    thread = threading.Thread(
        target=_send_verification_email,
        args=(user, raw_token),
        daemon=True,
    )
    thread.start()
