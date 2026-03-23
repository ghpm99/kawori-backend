from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from kawori.decorators import validate_user
from user_profile.application.use_cases.user_groups import UserGroupsUseCase
from user_profile.application.use_cases.user_view import UserViewUseCase


@require_GET
@validate_user("user")
def user_view(request: HttpRequest, user: User) -> JsonResponse:
    payload = UserViewUseCase().execute(user=user)
    return JsonResponse(payload)


@require_GET
@validate_user("user")
def user_groups(request: HttpRequest, user: User) -> JsonResponse:
    payload = UserGroupsUseCase().execute(user=user)
    return JsonResponse(payload)
