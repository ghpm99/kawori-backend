from http import HTTPStatus
import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from authentication.models import EmailVerification, UserToken
from authentication.utils import (
    get_client_ip,
    register_groups,
    send_password_reset_email_async,
    send_verification_email_async,
)
from audit.decorators import audit_log, audit_log_auth
from audit.models import CATEGORY_AUTH
from kawori.decorators import validate_user


@require_POST
@audit_log_auth("login")
def obtain_token_pair(request: HttpRequest) -> JsonResponse:
    req = json.loads(request.body)
    err = []

    if not req.get("username"):
        err.append({"username": "Este campo é obrigatório"})
    if not req.get("password"):
        err.append({"password": "Este campo é obrigatório"})
    if err:
        return JsonResponse({"errors": err}, status=HTTPStatus.BAD_REQUEST)

    user = authenticate(username=req.get("username"), password=req.get("password"))

    if not user:
        return JsonResponse({"msg": "Dados incorretos."}, status=HTTPStatus.NOT_FOUND)
    if not user.is_active:
        return JsonResponse({"msg": "Este usuário não está ativo."}, status=HTTPStatus.FORBIDDEN)

    if user.last_login:
        user.last_login = datetime.now(tz=user.last_login.tzinfo)
    else:
        user.last_login = datetime.now(tz=timezone.utc)

    user.save()
    access_token = AccessToken.for_user(user)
    refresh_token = RefreshToken.for_user(user)
    refresh_token_expiration = datetime.fromtimestamp(refresh_token["exp"], tz=timezone.utc)

    response = JsonResponse({"refresh_token_expiration": refresh_token_expiration.isoformat()})

    response.set_cookie(
        settings.ACCESS_TOKEN_NAME,
        str(access_token),
        httponly=True,
        secure=True,
        samesite="Strict",
        max_age=access_token.lifetime.total_seconds(),
        domain=settings.COOKIE_DOMAIN,
    )

    response.set_cookie(
        settings.REFRESH_TOKEN_NAME,
        str(refresh_token),
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=refresh_token.lifetime.total_seconds(),
        path=reverse("da_token_refresh"),
        domain=settings.COOKIE_DOMAIN,
    )

    response.set_cookie(
        "lifetimetoken",
        refresh_token_expiration.isoformat(),
        httponly=True,
        secure=True,
        samesite="None",
        max_age=refresh_token.lifetime.total_seconds(),
        domain=settings.COOKIE_DOMAIN,
    )

    return response


@require_GET
@audit_log_auth("logout")
def signout_view(request: HttpRequest) -> JsonResponse:
    response = JsonResponse({"msg": "Deslogou"})

    response.delete_cookie(
        settings.ACCESS_TOKEN_NAME,
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        settings.REFRESH_TOKEN_NAME,
        path=reverse("da_token_refresh"),
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        "lifetimetoken",
        domain=settings.COOKIE_DOMAIN,
    )

    return response


@require_POST
@audit_log_auth("token.verify")
def verify_token(request: HttpRequest) -> JsonResponse:

    access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)

    if access_token_cookie is None:
        return JsonResponse({"msg": "Token não encontrado"}, status=HTTPStatus.BAD_REQUEST)

    try:

        token = AccessToken(access_token_cookie)
        token.verify()
        token.verify_token_type()

        return JsonResponse({"msg": "Token válido"})

    except Exception as e:

        json_response = JsonResponse({"error": str(e), "valid": False}, status=HTTPStatus.UNAUTHORIZED)

        json_response.delete_cookie(
            settings.ACCESS_TOKEN_NAME,
            domain=settings.COOKIE_DOMAIN,
        )
        return json_response


@require_POST
@audit_log_auth("token.refresh")
def refresh_token(request: HttpRequest) -> JsonResponse:

    refresh_token_cookie = request.COOKIES.get(settings.REFRESH_TOKEN_NAME)
    if refresh_token_cookie is None:
        return JsonResponse({"msg": "Token não encontrado"}, status=HTTPStatus.FORBIDDEN)

    try:
        refresh_token = RefreshToken(refresh_token_cookie)
        refresh_token.verify()
        refresh_token.verify_token_type()

        access_token = refresh_token.access_token

        json_response = JsonResponse({"msg": "Token válido"})
        json_response.set_cookie(
            settings.ACCESS_TOKEN_NAME,
            str(access_token),
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=access_token.lifetime.total_seconds(),
            domain=settings.COOKIE_DOMAIN,
        )

        return json_response
    except Exception as e:
        return JsonResponse({"error": str(e), "valid": False}, status=HTTPStatus.FORBIDDEN)


@require_POST
@audit_log_auth("signup")
def signup_view(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)

    required_fields = ["username", "password", "email", "name", "last_name"]
    for field in required_fields:
        if not data.get(field):
            return JsonResponse({"msg": "Todos os campos são obrigatórios."}, status=HTTPStatus.BAD_REQUEST)

    username = data["username"]
    password = data["password"]
    email = data["email"]
    name = data["name"]
    last_name = data["last_name"]

    username_exists = User.objects.filter(username=username).exists()

    if username_exists:
        return JsonResponse({"msg": "Usuário já cadastrado"}, status=HTTPStatus.BAD_REQUEST)

    email_exists = User.objects.filter(email=email).exists()

    if email_exists:
        return JsonResponse({"msg": "E-mail já cadastrado"}, status=HTTPStatus.BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password, email=email)
    user.first_name = name
    user.last_name = last_name
    user.save()

    register_groups(user)

    try:
        from budget.services import create_default_budgets_for_user

        create_default_budgets_for_user(user)
    except Exception:
        pass

    EmailVerification.objects.create(user=user)

    try:
        ip_address = get_client_ip(request)
        raw_token = UserToken.create_for_user(
            user, token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION, ip_address=ip_address
        )
        send_verification_email_async(user, raw_token)
    except Exception:
        pass

    return JsonResponse({"msg": "Usuário criado com sucesso!"})


@ensure_csrf_cookie
def obtain_csrf_cookie(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"msg": "Token registrado"})


# ─── Password reset ───────────────────────────────────────────────────────────

_RESET_GENERIC_MSG = "Se o e-mail estiver cadastrado, você receberá as instruções em breve."


@require_POST
@audit_log_auth("password_reset.request")
def request_password_reset(request: HttpRequest) -> JsonResponse:
    """
    Solicita a redefinição de senha.
    Gera um token único com expiração e envia o e-mail de forma assíncrona.
    Retorna sempre a mesma mensagem genérica para evitar enumeração de usuários.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST)

    email = data.get("email", "").strip().lower()
    if not email:
        return JsonResponse({"msg": "E-mail é obrigatório."}, status=HTTPStatus.BAD_REQUEST)

    ip_address = get_client_ip(request)

    if UserToken.is_rate_limited_by_ip(ip_address, UserToken.TOKEN_TYPE_PASSWORD_RESET):
        return JsonResponse(
            {"msg": "Muitas tentativas. Tente novamente mais tarde."},
            status=429,
        )

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"msg": _RESET_GENERIC_MSG})

    if UserToken.is_rate_limited_by_user(user, UserToken.TOKEN_TYPE_PASSWORD_RESET):
        return JsonResponse({"msg": _RESET_GENERIC_MSG})

    raw_token = UserToken.create_for_user(user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address=ip_address)
    send_password_reset_email_async(user, raw_token)

    return JsonResponse({"msg": _RESET_GENERIC_MSG})


@require_GET
@audit_log_auth("password_reset.validate")
def validate_reset_token(request: HttpRequest) -> JsonResponse:
    """
    Valida se um token de reset ainda é válido (não usado e não expirado).
    Usado pelo frontend para verificar o token antes de exibir o formulário de nova senha.
    """
    raw_token = request.GET.get("token", "").strip()
    if not raw_token:
        return JsonResponse(
            {"valid": False, "msg": "Token é obrigatório."},
            status=HTTPStatus.BAD_REQUEST,
        )

    token_hash = UserToken.hash_token(raw_token)

    try:
        token_obj = UserToken.objects.get(
            token_hash=token_hash, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET
        )
    except UserToken.DoesNotExist:
        return JsonResponse(
            {"valid": False, "msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not token_obj.is_valid():
        return JsonResponse(
            {"valid": False, "msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    return JsonResponse({"valid": True})


@require_POST
@audit_log_auth("password_reset.confirm")
def confirm_password_reset(request: HttpRequest) -> JsonResponse:
    """
    Confirma a redefinição de senha com o token recebido por e-mail.
    Valida token, aplica regras de senha do Django e invalida o token após uso.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST)

    raw_token = data.get("token", "").strip()
    new_password = data.get("new_password", "")

    if not raw_token or not new_password:
        return JsonResponse(
            {"msg": "Token e nova senha são obrigatórios."},
            status=HTTPStatus.BAD_REQUEST,
        )

    token_hash = UserToken.hash_token(raw_token)

    try:
        token_obj = UserToken.objects.select_related("user").get(
            token_hash=token_hash, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET
        )
    except UserToken.DoesNotExist:
        return JsonResponse(
            {"msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not token_obj.is_valid():
        return JsonResponse(
            {"msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    user = token_obj.user

    try:
        validate_password(new_password, user)
    except ValidationError as e:
        return JsonResponse({"msg": list(e.messages)}, status=HTTPStatus.BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=["password"])

    ip_address = get_client_ip(request)
    token_obj.consume(ip_address)

    return JsonResponse({"msg": "Senha redefinida com sucesso."})


# ─── Email verification ──────────────────────────────────────────────────────


@require_POST
@audit_log_auth("email.verify")
def verify_email(request: HttpRequest) -> JsonResponse:
    """
    Verifica o email do usuário usando o token recebido por email.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST)

    raw_token = data.get("token", "").strip()
    if not raw_token:
        return JsonResponse({"msg": "Token é obrigatório."}, status=HTTPStatus.BAD_REQUEST)

    token_hash = UserToken.hash_token(raw_token)

    try:
        token_obj = UserToken.objects.select_related("user").get(
            token_hash=token_hash, token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION
        )
    except UserToken.DoesNotExist:
        return JsonResponse(
            {"msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not token_obj.is_valid():
        return JsonResponse(
            {"msg": "Token inválido ou expirado."},
            status=HTTPStatus.BAD_REQUEST,
        )

    user = token_obj.user

    verification, _ = EmailVerification.objects.get_or_create(user=user)
    verification.is_verified = True
    verification.verified_at = timezone.now()
    verification.save(update_fields=["is_verified", "verified_at"])

    ip_address = get_client_ip(request)
    token_obj.consume(ip_address)

    return JsonResponse({"msg": "Email verificado com sucesso."})


@require_POST
@validate_user("user")
@audit_log("email.resend_verification", CATEGORY_AUTH)
def resend_verification_email(request: HttpRequest, user: User) -> JsonResponse:
    """
    Reenvia o email de verificação para o usuário autenticado.
    """
    try:
        verification = EmailVerification.objects.get(user=user)
    except EmailVerification.DoesNotExist:
        verification = EmailVerification.objects.create(user=user)

    if verification.is_verified:
        return JsonResponse({"msg": "Email já verificado."})

    if UserToken.is_rate_limited_by_user(user, UserToken.TOKEN_TYPE_EMAIL_VERIFICATION):
        return JsonResponse(
            {"msg": "Muitas tentativas. Tente novamente mais tarde."},
            status=429,
        )

    ip_address = get_client_ip(request)
    raw_token = UserToken.create_for_user(
        user, token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION, ip_address=ip_address
    )
    send_verification_email_async(user, raw_token)

    return JsonResponse({"msg": "Email de verificação reenviado."})
