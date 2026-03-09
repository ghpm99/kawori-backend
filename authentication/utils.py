import re
import threading
from datetime import datetime
from smtplib import SMTP
from urllib.parse import urlencode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
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


class SocialOAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


SOCIAL_PROVIDER_DEFINITIONS = {
    "google": {
        "display_name": "Google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",  # nosec B105
        "scopes": ["openid", "email", "profile"],
    },
    "discord": {
        "display_name": "Discord",
        "auth_url": "https://discord.com/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",  # nosec B105
        "scopes": ["identify", "email"],
    },
    "github": {
        "display_name": "GitHub",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",  # nosec B105
        "scopes": ["read:user", "user:email"],
    },
    "facebook": {
        "display_name": "Facebook",
        "auth_url": "https://www.facebook.com/v20.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v20.0/oauth/access_token",  # nosec B105
        "scopes": ["email", "public_profile"],
    },
    "microsoft": {
        "display_name": "Microsoft",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",  # nosec B105
        "scopes": ["openid", "profile", "email", "User.Read"],
    },
}


def slugify_username(value: str) -> str:
    safe_value = re.sub(r"[^a-zA-Z0-9_]+", "_", (value or "").strip().lower()).strip("_")
    return safe_value or "user"


def generate_unique_username(base_value: str) -> str:
    base = slugify_username(base_value)[:120]
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base[:110]}_{suffix}"
    return username


def split_name(full_name: str) -> tuple[str, str]:
    value = (full_name or "").strip()
    if not value:
        return "", ""
    parts = value.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def social_provider_is_enabled(provider: str) -> bool:
    provider_conf = settings.SOCIAL_AUTH_PROVIDERS.get(provider, {})
    return bool(provider_conf.get("client_id") and provider_conf.get("client_secret"))


def list_enabled_social_providers() -> list[dict]:
    providers = []
    for provider_key, definition in SOCIAL_PROVIDER_DEFINITIONS.items():
        if social_provider_is_enabled(provider_key):
            providers.append(
                {
                    "provider": provider_key,
                    "name": definition["display_name"],
                    "scopes": definition["scopes"],
                }
            )
    return providers


def get_social_provider_config(provider: str) -> dict:
    provider = (provider or "").strip().lower()
    if provider not in SOCIAL_PROVIDER_DEFINITIONS:
        raise SocialOAuthError("Provedor social não suportado.", status_code=404)

    env_conf = settings.SOCIAL_AUTH_PROVIDERS.get(provider, {})
    client_id = env_conf.get("client_id")
    client_secret = env_conf.get("client_secret")
    if not client_id or not client_secret:
        raise SocialOAuthError("Provedor social indisponível.", status_code=404)

    return {
        **SOCIAL_PROVIDER_DEFINITIONS[provider],
        "provider": provider,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def build_social_authorize_url(provider_config: dict, state: str, redirect_uri: str) -> str:
    query = {
        "client_id": provider_config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(provider_config["scopes"]),
        "state": state,
    }
    return f"{provider_config['auth_url']}?{urlencode(query)}"


def exchange_social_code_for_token(provider_config: dict, code: str, redirect_uri: str) -> dict:
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": provider_config["client_id"],
        "client_secret": provider_config["client_secret"],
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(provider_config["token_url"], data=payload, headers=headers, timeout=12)
    if response.status_code >= 400:
        raise SocialOAuthError("Falha ao trocar o código OAuth.", status_code=400)

    token_data = response.json()
    if not token_data.get("access_token"):
        raise SocialOAuthError("Provedor não retornou access token.", status_code=400)

    return token_data


def fetch_social_profile(provider_config: dict, token_data: dict) -> dict:
    provider = provider_config["provider"]
    access_token = token_data["access_token"]

    if provider == "google":
        response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
        payload = response.json()
        return {
            "provider_user_id": str(payload.get("sub", "")),
            "email": payload.get("email", "") or "",
            "is_email_verified": bool(payload.get("email_verified")),
            "full_name": payload.get("name", "") or "",
            "avatar_url": payload.get("picture", "") or "",
            "raw": payload,
        }

    if provider == "discord":
        response = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
        payload = response.json()
        avatar = payload.get("avatar")
        avatar_url = f"https://cdn.discordapp.com/avatars/{payload.get('id')}/{avatar}.png" if avatar else ""
        return {
            "provider_user_id": str(payload.get("id", "")),
            "email": payload.get("email", "") or "",
            "is_email_verified": bool(payload.get("verified")),
            "full_name": payload.get("global_name") or payload.get("username", ""),
            "avatar_url": avatar_url,
            "raw": payload,
        }

    if provider == "github":
        response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            timeout=12,
        )
        payload = response.json()
        email = payload.get("email") or ""
        is_verified = bool(email)
        if not email:
            email_response = requests.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
                timeout=12,
            )
            email_payload = email_response.json() if email_response.status_code < 400 else []
            if isinstance(email_payload, list):
                primary_verified = next(
                    (
                        item
                        for item in email_payload
                        if item.get("email") and item.get("primary") and item.get("verified")
                    ),
                    None,
                )
                if primary_verified:
                    email = primary_verified.get("email", "")
                    is_verified = True

        return {
            "provider_user_id": str(payload.get("id", "")),
            "email": email,
            "is_email_verified": is_verified,
            "full_name": payload.get("name") or payload.get("login", ""),
            "avatar_url": payload.get("avatar_url", "") or "",
            "raw": payload,
        }

    if provider == "facebook":
        response = requests.get(
            "https://graph.facebook.com/me",
            params={"fields": "id,name,email,picture.type(large)", "access_token": access_token},
            timeout=12,
        )
        payload = response.json()
        picture_data = (payload.get("picture") or {}).get("data") or {}
        return {
            "provider_user_id": str(payload.get("id", "")),
            "email": payload.get("email", "") or "",
            "is_email_verified": bool(payload.get("email")),
            "full_name": payload.get("name", "") or "",
            "avatar_url": picture_data.get("url", "") or "",
            "raw": payload,
        }

    if provider == "microsoft":
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=12,
        )
        payload = response.json()
        email = payload.get("mail") or payload.get("userPrincipalName") or ""
        return {
            "provider_user_id": str(payload.get("id", "")),
            "email": email,
            "is_email_verified": bool(email),
            "full_name": payload.get("displayName", "") or "",
            "avatar_url": "",
            "raw": payload,
        }

    raise SocialOAuthError("Provedor social não suportado.", status_code=404)


def parse_iso_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_social_redirect_url(base_url: str, params: dict) -> str:
    if not base_url:
        return ""
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


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
