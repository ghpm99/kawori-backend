from http import HTTPStatus
import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from authentication.utils import register_groups


@require_POST
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
def verify_token(request: HttpRequest) -> JsonResponse:

    access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)

    if access_token_cookie is None:
        return JsonResponse({"msg": "Token não encontrado"}, status=HTTPStatus.UNAUTHORIZED)

    try:

        token = AccessToken(access_token_cookie)
        token.verify()
        token.verify_token_type()

        return JsonResponse({"msg": "Token válido"})

    except Exception as e:

        json_response = JsonResponse({
            "error": str(e),
            "valid": False
        }, status=HTTPStatus.UNAUTHORIZED)

        json_response.delete_cookie(
            settings.ACCESS_TOKEN_NAME,
            domain=settings.COOKIE_DOMAIN,
        )
        return json_response


@require_POST
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

    return JsonResponse({"msg": "Usuário criado com sucesso!"})


@ensure_csrf_cookie
def obtain_csrf_cookie(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"msg": "Token registrado"})
