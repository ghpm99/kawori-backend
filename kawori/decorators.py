from functools import wraps
from typing import Iterable
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from authentication.utils import refresh_access_token


def add_cors_react_dev(func):
    def add_cors_react_dev_response(response):

        response["Access-Control-Allow-Origin"] = settings.BASE_URL_FRONTEND
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "*"
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept, Origin, User-Agent, Referer, Host, Connection, Access-Control-Request-Method, Access-Control-Request-Headers, access-control-allow-origin"
        )

        return response

    def inner(request, *args, **kwargs):
        if request.method == "OPTIONS":
            return add_cors_react_dev_response(HttpResponse("Ok"))

        result = add_cors_react_dev_response(func(request, *args, **kwargs))
        return result

    return inner


def validate_user(group: str):

    def decorator(view_func):

        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            expired_token = True

            access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)
            refresh_token_cookie = request.COOKIES.get(settings.REFRESH_TOKEN_NAME)

            print("==================cookies================")
            print(access_token_cookie)
            print(refresh_token_cookie)
            print("=========================================")

            if not access_token_cookie and not refresh_token_cookie:
                return JsonResponse({"msg": "Empty authorization."}, status=403)

            user_data = {}

            try:

                access_token = AccessToken(access_token_cookie) if access_token_cookie else None
                refresh_token = RefreshToken(refresh_token_cookie) if refresh_token_cookie else None

                print("==================user data================")
                print("user data access_token", access_token.payload if access_token else None)
                print("user data refresh_token", refresh_token.payload if refresh_token else None)
                print("=========================================")

                user_data = refresh_token if access_token is None else access_token

            except Exception as err:
                return JsonResponse({"msg": str(err)}, status=401)

            user_id = user_data.get("user_id")

            print("user_data", user_data.payload)
            print("user_id", user_id)

            if not user_id:
                return JsonResponse({"msg": "User not found."}, status=403)

            user = User.objects.get(id=user_id)

            if not user:
                return JsonResponse({"msg": "User not found."}, status=403)
            if not user.is_active:
                return JsonResponse({"msg": "User not active."}, status=403)

            if not user.groups.filter(name=group).exists():
                return JsonResponse({"msg": "User does not have permission to access this module."}, status=403)



            return view_func(request, user=user, *args, **kwargs)

        return _wrapped_view

    return decorator


def validate_super_user(func):
    """
    `validate_user` is a decorator that blocks users that are not active or staff.

    - It's necessary to pass user `id` and `username` in the header authorization.
    Example: `Authorization: Basic <base64(user_id|username)>`;
    - It's necessary to pass the parameter `user` on the view where this decorator will be called,
    even if this parameter will be not used.
    """

    def inner(request, *args, **kwargs):
        token = request.META.get("HTTP_AUTHORIZATION")[7:] if request.META.get("HTTP_AUTHORIZATION") else None
        user_data = {}

        if not token:
            return JsonResponse({"msg": "Empty authorization."}, status=403)

        try:
            user_data = AccessToken(token)
        except Exception as err:
            return JsonResponse({"msg": str(err)}, status=401)

        user_id = user_data.get("user_id")
        user = User.objects.get(id=user_id)

        if not user:
            return JsonResponse({"msg": "User not found."}, status=404)

        if not user.is_active:
            return JsonResponse({"msg": "User not active."}, status=403)

        if not user.is_staff:
            return JsonResponse({"msg": "Este usuário não possui permissão para acessar este módulo."}, status=403)

        return func(request, user=user, *args, **kwargs)

    return inner


def validate_token(func):
    """
    `validate_token` is a decorator to check if a bearer token is valid and is active.

    - It's necessary to pass user the bearer token in the header authorization.
    Example: `Authorization: Bearer <token>`;
    - The access token can be obtained on the path `/auth/token/` on the API;
    - It's necessary to pass the parameter `user` on the view where this decorator will be called,
    even if this parameter will be not used.
    """

    def inner(request, *args, **kwargs):
        token = request.META.get("HTTP_AUTHORIZATION")[7:] if request.META.get("HTTP_AUTHORIZATION") else None
        user_data = {}

        if not token:
            return JsonResponse({"msg": "Empty authorization."}, status=403)

        try:
            user_data = AccessToken(token)
        except Exception as err:
            return JsonResponse({"msg": str(err)}, status=401)

        user_id = user_data.get("user_id")
        user = User.objects.get(id=user_id)

        if not user:
            return JsonResponse({"msg": "User not found."}, status=404)

        if not user.is_active:
            return JsonResponse({"msg": "User not active."}, status=403)

        return func(request, user=user, *args, **kwargs)

    return inner


def validate_token_admin(func):
    """
    `validate_token_admin` is a decorator to check if a bearer token is valid and is active.

    - It's necessary to pass user the bearer token in the header authorization.
    Example: `Authorization: Bearer <token>`;
    - The access token can be obtained on the path `/auth/token/` on the API;
    - It's necessary to pass the parameter `user` on the view where this decorator will be called,
    even if this parameter will be not used.
    """

    def inner(request, *args, **kwargs):
        token = request.META.get("HTTP_AUTHORIZATION")[7:] if request.META.get("HTTP_AUTHORIZATION") else None
        user_data = {}

        if not token:
            return JsonResponse({"msg": "Empty authorization."}, status=403)

        try:
            user_data = AccessToken(token)
        except Exception as err:
            return JsonResponse({"msg": str(err)}, status=401)

        user_id = user_data.get("user_id")
        user = User.objects.get(id=user_id)

        if not user:
            return JsonResponse({"msg": "User not found."}, status=404)

        if not user.is_active:
            return JsonResponse({"msg": "User not active."}, status=403)

        if not user.is_staff:
            return JsonResponse({"msg": "Este usuário não possui permissão para acessar este módulo."}, status=403)

        return func(request, user=user, *args, **kwargs)

    return inner


def move_cookie_token_to_header(func):
    def inner(request, *args, **kwargs):
        access_token = request.cookies.get(settings.ACCESS_TOKEN_NAME)

        if access_token is not None:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"

        return func(request, *args, **kwargs)

    return inner
