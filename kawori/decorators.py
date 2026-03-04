from functools import wraps
from http import HTTPStatus
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from rest_framework_simplejwt.tokens import AccessToken


def validate_user(group: str):

    def decorator(view_func):

        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):

            access_token_cookie = request.COOKIES.get(settings.ACCESS_TOKEN_NAME)

            if not access_token_cookie:
                return JsonResponse({"msg": "Empty authorization."}, status=HTTPStatus.UNAUTHORIZED)

            user_data = {}

            try:

                access_token = AccessToken(access_token_cookie)
                access_token.verify()
                access_token.verify_token_type()

                user_data = access_token

            except Exception:
                return JsonResponse({"msg": "Invalid authorization token."}, status=HTTPStatus.UNAUTHORIZED)

            user_id = user_data.get("user_id")

            if not user_id:
                return JsonResponse({"msg": "User not found."}, status=HTTPStatus.FORBIDDEN)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({"msg": "User not found."}, status=HTTPStatus.FORBIDDEN)
            if not user.is_active:
                return JsonResponse({"msg": "User not active."}, status=HTTPStatus.FORBIDDEN)

            if not user.groups.filter(name=group).exists():
                return JsonResponse(
                    {"msg": "User does not have permission to access this module."}, status=HTTPStatus.FORBIDDEN
                )

            return view_func(request, user=user, *args, **kwargs)

        return _wrapped_view

    return decorator
