from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from analytics.application.use_cases.get_new_users import GetNewUsersUseCase
from analytics.interfaces.api.serializers.new_users_serializers import (
    NewUsersResponseSerializer,
)
from kawori.decorators import validate_user


# Create your views here.
@require_GET
@validate_user("financial")
def get_new_users(request, user):
    payload, status_code = GetNewUsersUseCase().execute(
        user_model=User,
        datetime_cls=datetime,
        timedelta_cls=timedelta,
    )
    serializer = NewUsersResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
