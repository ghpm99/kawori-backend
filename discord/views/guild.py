from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from discord.application.use_cases.get_all_guilds import GetAllGuildsUseCase
from discord.interfaces.api.serializers.guild_serializers import (
    GetAllGuildsResponseSerializer,
)
from kawori.decorators import validate_user
from kawori.utils import paginate


@require_GET
@validate_user("admin")
def get_all_members(request, user):
    req = request.GET

    query = """
        SELECT id,
            banned,
            id_discord,
            id_guild_discord,
            id_user_discord,
            nick
        FROM member_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        members = cursor.fetchall()

    members = [
        {
            "id": member[0],
            "banned": member[1],
            "id_discord": member[2],
            "id_guild_discord": member[3],
            "id_user_discord": member[4],
            "nick": member[5],
        }
        for member in members
    ]

    members = paginate(members, req.get("page"))
    return JsonResponse(members)


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
    req = request.GET

    query = """
        SELECT id,
            active
        FROM role_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        roles = cursor.fetchall()

    roles = [
        {
            "id": role[0],
            "active": role[1],
        }
        for role in roles
    ]

    roles = paginate(roles, req.get("page"))
    return JsonResponse(roles)
