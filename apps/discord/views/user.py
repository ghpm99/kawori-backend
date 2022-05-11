
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
        SELECT * FROM member_discord;
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
# @validate_user
@require_GET
def get_all_users(request):
    req = request.GET

    query = """
        SELECT * FROM user_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        users=cursor.fetchall()

    users= [{
        'id': user[0],
        'banned': user[1],
        'cmd_count': user[2],
        'discriminator': user[3],
        'exp': user[4],
        'exp_required': user[5],
        'id_discord': user[6],
        'last_message': user[7],
        'level': user[8],
        'msg_count': user[9],
        'name': user[10],
        'region': user[11],
        'role': user[12],
        'web_authorized': user[13]
    } for user in users]

    users = paginate(users, req.get('page'))
    return JsonResponse(users)
