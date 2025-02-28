from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from kawori.decorators import validate_user
from kawori.utils import paginate


@require_GET
@validate_user("discord")
def get_all_users(request, user):
    req = request.GET

    query = """
        SELECT id,
            banned,
            discriminator,
            id_discord,
            last_message,
            name
        FROM user_discord;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        users = cursor.fetchall()

    users = [
        {
            "id": user[0],
            "banned": user[1],
            "discriminator": user[2],
            "id_discord": user[3],
            "last_message": user[4],
            "name": user[5],
        }
        for user in users
    ]

    users = paginate(users, req.get("page"))
    return JsonResponse(users)
