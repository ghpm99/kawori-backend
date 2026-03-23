from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from discord.application.use_cases.get_all_users import GetAllUsersUseCase
from discord.interfaces.api.serializers.user_serializers import (
    GetAllUsersResponseSerializer,
)
from kawori.decorators import validate_user
from kawori.utils import paginate


@require_GET
@validate_user("discord")
def get_all_users(request, user):
    payload, status_code = GetAllUsersUseCase().execute(
        request_get=request.GET,
        connection_module=connection,
        paginate_fn=paginate,
    )
    serializer = GetAllUsersResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
