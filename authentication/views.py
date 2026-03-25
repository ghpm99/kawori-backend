import json
from datetime import datetime
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from audit.decorators import audit_log, audit_log_auth
from audit.models import CATEGORY_AUTH
from authentication.application.use_cases.confirm_password_reset import (
    ConfirmPasswordResetUseCase,
)
from authentication.application.use_cases.obtain_csrf_cookie import (
    ObtainCsrfCookieUseCase,
)
from authentication.application.use_cases.obtain_token_pair import (
    ObtainTokenPairUseCase,
)
from authentication.application.use_cases.refresh_token import RefreshTokenUseCase
from authentication.application.use_cases.request_password_reset import (
    RequestPasswordResetUseCase,
)
from authentication.application.use_cases.resend_verification_email import (
    ResendVerificationEmailUseCase,
)
from authentication.application.use_cases.signout import SignoutUseCase
from authentication.application.use_cases.signup import SignupUseCase
from authentication.application.use_cases.social_account_unlink import (
    SocialAccountUnlinkUseCase,
)
from authentication.application.use_cases.social_accounts_list import (
    SocialAccountsListUseCase,
)
from authentication.application.use_cases.social_authorize import (
    SocialAuthorizeUseCase,
)
from authentication.application.use_cases.social_callback import SocialCallbackUseCase
from authentication.application.use_cases.social_providers import (
    SocialProvidersUseCase,
)
from authentication.application.use_cases.validate_reset_token import (
    ValidateResetTokenUseCase,
)
from authentication.application.use_cases.verify_email import VerifyEmailUseCase
from authentication.application.use_cases.verify_token import VerifyTokenUseCase
from authentication.interfaces.api.serializers.obtain_csrf_cookie_serializers import (
    ObtainCsrfCookieResponseSerializer,
)
from authentication.interfaces.api.serializers.obtain_token_pair_serializers import (
    ObtainTokenPairRequestSerializer,
)
from authentication.interfaces.api.serializers.password_reset_confirm_serializers import (
    PasswordResetConfirmSerializer,
)
from authentication.interfaces.api.serializers.password_reset_request_serializers import (
    PasswordResetRequestSerializer,
)
from authentication.interfaces.api.serializers.password_reset_validate_serializers import (
    PasswordResetValidateSerializer,
)
from authentication.interfaces.api.serializers.refresh_token_serializers import (
    RefreshTokenResponseSerializer,
)
from authentication.interfaces.api.serializers.resend_verification_email_serializers import (
    ResendVerificationEmailResponseSerializer,
)
from authentication.interfaces.api.serializers.signout_serializers import (
    SignoutResponseSerializer,
)
from authentication.interfaces.api.serializers.signup_serializers import (
    SignupRequestSerializer,
)
from authentication.interfaces.api.serializers.social_account_unlink_serializers import (
    SocialAccountUnlinkResponseSerializer,
)
from authentication.interfaces.api.serializers.social_accounts_list_serializers import (
    SocialAccountsListResponseSerializer,
)
from authentication.interfaces.api.serializers.social_authorize_serializers import (
    SocialAuthorizeResponseSerializer,
)
from authentication.interfaces.api.serializers.social_callback_serializers import (
    SocialCallbackQuerySerializer,
)
from authentication.interfaces.api.serializers.social_providers_serializers import (
    SocialProvidersResponseSerializer,
)
from authentication.interfaces.api.serializers.verify_email_serializers import (
    VerifyEmailSerializer,
)
from authentication.interfaces.api.serializers.verify_token_serializers import (
    VerifyTokenResponseSerializer,
)
from authentication.models import (
    EmailVerification,
    SocialAccount,
    SocialAuthState,
    UserToken,
)
from authentication.utils import (
    SocialOAuthError,
    build_social_authorize_url,
    build_social_redirect_url,
    exchange_social_code_for_token,
    fetch_social_profile,
    generate_unique_username,
    get_client_ip,
    get_social_provider_config,
    list_enabled_social_providers,
    register_groups,
    send_password_reset_email_async,
    send_verification_email_async,
    split_name,
)
from kawori.decorators import validate_user


def _build_auth_response(user: User, payload: dict = None) -> JsonResponse:
    if user.last_login:
        user.last_login = datetime.now(tz=user.last_login.tzinfo)
    else:
        user.last_login = datetime.now(tz=timezone.utc)
    user.save(update_fields=["last_login"])

    access_token = AccessToken.for_user(user)
    refresh_token = RefreshToken.for_user(user)
    refresh_token_expiration = datetime.fromtimestamp(
        refresh_token["exp"], tz=timezone.utc
    )

    response_payload = payload.copy() if payload else {}
    response_payload["refresh_token_expiration"] = refresh_token_expiration.isoformat()
    response = JsonResponse(response_payload)
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


def _get_current_user_from_cookie(request: HttpRequest):
    access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)
    if not access_token_cookie:
        return None

    try:
        token = AccessToken(access_token_cookie)
        token.verify()
        token.verify_token_type()
    except Exception:
        return None

    user_id = token.get("user_id")
    if not user_id:
        return None

    return User.objects.filter(id=user_id, is_active=True).first()


def _create_user_from_social_profile(profile: dict, provider: str) -> User:
    email = (profile.get("email") or "").strip().lower()
    full_name = (profile.get("full_name") or "").strip()
    first_name, last_name = split_name(full_name)
    base_username = (
        email.split("@")[0]
        if email
        else f"{provider}_{profile.get('provider_user_id', 'user')}"
    )
    username = generate_unique_username(base_username)

    user = User.objects.create_user(username=username, email=email, password=None)
    user.set_unusable_password()
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=["password", "first_name", "last_name", "email"])

    register_groups(user)

    try:
        from budget.services import create_default_budgets_for_user

        create_default_budgets_for_user(user)
    except Exception:  # nosec B110
        pass

    verification, _ = EmailVerification.objects.get_or_create(user=user)
    if profile.get("is_email_verified"):
        verification.is_verified = True
        verification.verified_at = timezone.now()
        verification.save(update_fields=["is_verified", "verified_at"])

    return user


def _redirect_or_json(
    state_obj: SocialAuthState, payload: dict, status_code: int = 200
):
    if state_obj and state_obj.frontend_redirect_uri:
        redirect_url = build_social_redirect_url(
            state_obj.frontend_redirect_uri, payload
        )
        return HttpResponseRedirect(redirect_url)
    return JsonResponse(payload, status=status_code)


@require_POST
@audit_log_auth("login")
def obtain_token_pair(request: HttpRequest) -> JsonResponse:
    req = json.loads(request.body)
    serializer = ObtainTokenPairRequestSerializer(data=req)
    serializer.is_valid(raise_exception=False)

    payload, status_code, user = ObtainTokenPairUseCase().execute(
        payload=req,
        authenticate_fn=authenticate,
    )
    if user is not None:
        return _build_auth_response(user, payload=payload)
    return JsonResponse(payload, status=status_code)


@require_GET
@audit_log_auth("logout")
def signout_view(request: HttpRequest) -> JsonResponse:
    payload, status_code, delete_cookie_instructions = SignoutUseCase().execute(
        access_token_name=settings.ACCESS_TOKEN_NAME,
        refresh_token_name=settings.REFRESH_TOKEN_NAME,
        cookie_domain=settings.COOKIE_DOMAIN,
        refresh_path=reverse("da_token_refresh"),
    )
    serializer = SignoutResponseSerializer(payload)
    response = JsonResponse(serializer.data, status=status_code)
    for instruction in delete_cookie_instructions:
        response.delete_cookie(**instruction)
    return response


@require_POST
@audit_log_auth("token.verify")
def verify_token(request: HttpRequest) -> JsonResponse:
    payload, status_code, should_delete_cookie = VerifyTokenUseCase().execute(
        access_token_cookie=request.COOKIES.get(settings.ACCESS_TOKEN_NAME),
        access_token_cls=AccessToken,
    )
    serializer = VerifyTokenResponseSerializer(payload)
    json_response = JsonResponse(serializer.data, status=status_code)
    if should_delete_cookie:
        json_response.delete_cookie(
            settings.ACCESS_TOKEN_NAME,
            domain=settings.COOKIE_DOMAIN,
        )
    return json_response


@require_POST
@audit_log_auth("token.refresh")
def refresh_token(request: HttpRequest) -> JsonResponse:
    payload, status_code, access_token = RefreshTokenUseCase().execute(
        refresh_token_cookie=request.COOKIES.get(settings.REFRESH_TOKEN_NAME),
        refresh_token_cls=RefreshToken,
    )
    serializer = RefreshTokenResponseSerializer(payload)
    json_response = JsonResponse(serializer.data, status=status_code)
    if access_token is not None:
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


@require_POST
@audit_log_auth("signup")
def signup_view(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)
    serializer = SignupRequestSerializer(data=data)
    serializer.is_valid(raise_exception=False)

    payload, status_code = SignupUseCase().execute(
        payload=data,
        request=request,
        user_model=User,
        transaction_module=transaction,
        register_groups_fn=register_groups,
        email_verification_model=EmailVerification,
        get_client_ip_fn=get_client_ip,
        user_token_model=UserToken,
        send_verification_email_async_fn=send_verification_email_async,
    )
    return JsonResponse(payload, status=status_code)


@ensure_csrf_cookie
def obtain_csrf_cookie(request: HttpRequest) -> JsonResponse:
    payload, status_code = ObtainCsrfCookieUseCase().execute()
    serializer = ObtainCsrfCookieResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


# ─── Password reset ───────────────────────────────────────────────────────────

_RESET_GENERIC_MSG = (
    "Se o e-mail estiver cadastrado, você receberá as instruções em breve."
)


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
        return JsonResponse(
            {"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST
        )

    serializer = PasswordResetRequestSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": "E-mail é obrigatório."}, status=HTTPStatus.BAD_REQUEST
        )

    payload, status_code = RequestPasswordResetUseCase().execute(
        email=serializer.validated_data["email"],
        request=request,
        user_model=User,
        user_token_model=UserToken,
        get_client_ip_fn=get_client_ip,
        send_password_reset_email_async_fn=send_password_reset_email_async,
        reset_generic_msg=_RESET_GENERIC_MSG,
    )
    return JsonResponse(payload, status=status_code)


@require_GET
@audit_log_auth("password_reset.validate")
def validate_reset_token(request: HttpRequest) -> JsonResponse:
    """
    Valida se um token de reset ainda é válido (não usado e não expirado).
    Usado pelo frontend para verificar o token antes de exibir o formulário de nova senha.
    """
    serializer = PasswordResetValidateSerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"valid": False, "msg": "Token é obrigatório."},
            status=HTTPStatus.BAD_REQUEST,
        )

    payload, status_code = ValidateResetTokenUseCase().execute(
        raw_token=serializer.validated_data["token"],
        user_token_model=UserToken,
    )
    return JsonResponse(payload, status=status_code)


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
        return JsonResponse(
            {"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST
        )

    serializer = PasswordResetConfirmSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": "Token e nova senha são obrigatórios."},
            status=HTTPStatus.BAD_REQUEST,
        )

    payload, status_code = ConfirmPasswordResetUseCase().execute(
        raw_token=serializer.validated_data["token"],
        new_password=serializer.validated_data["new_password"],
        request=request,
        user_token_model=UserToken,
        validate_password_fn=validate_password,
        validation_error_cls=ValidationError,
        transaction_module=transaction,
        get_client_ip_fn=get_client_ip,
    )
    return JsonResponse(payload, status=status_code)


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
        return JsonResponse(
            {"msg": "Requisição inválida."}, status=HTTPStatus.BAD_REQUEST
        )

    serializer = VerifyEmailSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": "Token é obrigatório."}, status=HTTPStatus.BAD_REQUEST
        )

    payload, status_code = VerifyEmailUseCase().execute(
        raw_token=serializer.validated_data["token"],
        request=request,
        user_token_model=UserToken,
        email_verification_model=EmailVerification,
        transaction_module=transaction,
        timezone_module=timezone,
        get_client_ip_fn=get_client_ip,
    )
    return JsonResponse(payload, status=status_code)


@require_POST
@validate_user("user")
@audit_log("email.resend_verification", CATEGORY_AUTH)
def resend_verification_email(request: HttpRequest, user: User) -> JsonResponse:
    """
    Reenvia o email de verificação para o usuário autenticado.
    """
    payload, status_code = ResendVerificationEmailUseCase().execute(
        user=user,
        request=request,
        email_verification_model=EmailVerification,
        user_token_model=UserToken,
        get_client_ip_fn=get_client_ip,
        send_verification_email_async_fn=send_verification_email_async,
    )
    serializer = ResendVerificationEmailResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


# ─── Social login ────────────────────────────────────────────────────────────


@require_GET
@audit_log_auth("social.providers")
def social_providers(request: HttpRequest) -> JsonResponse:
    payload, status_code = SocialProvidersUseCase().execute(
        list_enabled_social_providers_fn=list_enabled_social_providers
    )
    serializer = SocialProvidersResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@audit_log_auth("social.authorize")
def social_authorize(request: HttpRequest, provider: str) -> JsonResponse:
    payload, status_code = SocialAuthorizeUseCase().execute(
        request=request,
        provider=provider,
        get_social_provider_config_fn=get_social_provider_config,
        social_oauth_error_cls=SocialOAuthError,
        get_current_user_from_cookie_fn=_get_current_user_from_cookie,
        social_auth_state_model=SocialAuthState,
        social_auth_state_expiration_minutes=getattr(
            settings, "SOCIAL_AUTH_STATE_EXPIRATION_MINUTES", 10
        ),
        reverse_fn=reverse,
        build_social_authorize_url_fn=build_social_authorize_url,
    )
    serializer = SocialAuthorizeResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@audit_log_auth("social.callback")
def social_callback(request: HttpRequest, provider: str):
    serializer = SocialCallbackQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)
    return SocialCallbackUseCase().execute(
        request=request,
        provider=provider,
        social_oauth_error_cls=SocialOAuthError,
        get_social_provider_config_fn=get_social_provider_config,
        json_response_cls=JsonResponse,
        http_status_module=HTTPStatus,
        social_auth_state_model=SocialAuthState,
        reverse_fn=reverse,
        exchange_social_code_for_token_fn=exchange_social_code_for_token,
        fetch_social_profile_fn=fetch_social_profile,
        redirect_or_json_fn=_redirect_or_json,
        transaction_module=transaction,
        social_account_model=SocialAccount,
        user_model=User,
        create_user_from_social_profile_fn=_create_user_from_social_profile,
        timezone_module=timezone,
        email_verification_model=EmailVerification,
        build_auth_response_fn=_build_auth_response,
        http_response_redirect_cls=HttpResponseRedirect,
    )


@require_GET
@validate_user("user")
@audit_log("social.accounts.list", CATEGORY_AUTH)
def social_accounts_list(request: HttpRequest, user: User) -> JsonResponse:
    payload, status_code = SocialAccountsListUseCase().execute(
        user=user,
        social_account_model=SocialAccount,
    )
    serializer = SocialAccountsListResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_POST
@validate_user("user")
@audit_log("social.accounts.unlink", CATEGORY_AUTH)
def social_account_unlink(
    request: HttpRequest, user: User, provider: str
) -> JsonResponse:
    payload, status_code, account = SocialAccountUnlinkUseCase().execute(
        user=user,
        provider=provider,
        social_account_model=SocialAccount,
    )
    if account is not None:
        account.delete()
    serializer = SocialAccountUnlinkResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
