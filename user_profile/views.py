from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from kawori.decorators import add_cors_react_dev, validate_user


# Create your views here.
@csrf_exempt
@add_cors_react_dev
@validate_user
@require_GET
def user_view(request: HttpRequest, user: User) -> JsonResponse:

    return JsonResponse({
        'id': user.id,
        'name': user.get_full_name(),
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'last_login': user.last_login,
        'date_joined': user.date_joined,
    })
