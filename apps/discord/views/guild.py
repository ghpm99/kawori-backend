
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from kawori.decorators import add_cors_react_dev, validate_user
from kawori.utils import paginate


@add_cors_react_dev
# @validate_user
@require_GET
def get_all_members(request):
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
        members=cursor.fetchall()

    members= [{
        'id': member[0],
        'banned': member[1],
        'id_discord': member[2],
        'id_guild_discord': member[3],
        'id_user_discord': member[4],
        'nick': member[5]
    } for member in members]

    members = paginate(members, req.get('page'))
    return JsonResponse(members)


@add_cors_react_dev
@require_GET
def get_all_guilds(request):
    req = request.GET

    query = """
        SELECT id,
            active,
            block,
            id_discord,
            id_owner,
            last_message,
            name
        FROM guild_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        guilds=cursor.fetchall()

    guilds= [{
        'id': guild[0],
        'active': guild[1],
        'block': guild[2],
        'id_discord': guild[3],
        'id_owner': guild[4],
        'last_message': guild[5],
        'name': guild[6],
    } for guild in guilds]

    guilds = paginate(guilds, req.get('page'))
    return JsonResponse(guilds)


@add_cors_react_dev
@require_GET
def get_all_roles(request):
    req = request.GET

    query = """
        SELECT id,
            active
        FROM role_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        roles=cursor.fetchall()

    roles= [{
        'id': role[0],
        'active': role[1],
    } for role in roles]

    roles = paginate(roles, req.get('page'))
    return JsonResponse(roles)
