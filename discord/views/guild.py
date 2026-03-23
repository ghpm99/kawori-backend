from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from discord.application.use_cases.get_all_guilds import GetAllGuildsUseCase
from discord.application.use_cases.get_all_members import GetAllMembersUseCase
from discord.application.use_cases.get_all_roles import GetAllRolesUseCase
from discord.interfaces.api.serializers.guild_serializers import (
    GetAllGuildsResponseSerializer,
    GetAllMembersResponseSerializer,
    GetAllRolesResponseSerializer,
)
from kawori.decorators import validate_user
from kawori.utils import paginate


@require_GET
@validate_user("admin")
def get_all_members(request, user):
    payload, status_code = GetAllMembersUseCase().execute(
        request_get=request.GET,
        connection_module=connection,
        paginate_fn=paginate,
    )
    serializer = GetAllMembersResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def get_all_guilds(request, user):
    payload, status_code = GetAllGuildsUseCase().execute(
        request_get=request.GET,
        connection_module=connection,
        paginate_fn=paginate,
    )
    serializer = GetAllGuildsResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)


@require_GET
@validate_user("admin")
def get_all_roles(request, user):
    payload, status_code = GetAllRolesUseCase().execute(
        request_get=request.GET,
        connection_module=connection,
        paginate_fn=paginate,
    )
    serializer = GetAllRolesResponseSerializer(payload)
    return JsonResponse(serializer.data, status=status_code)
