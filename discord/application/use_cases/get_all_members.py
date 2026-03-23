class GetAllMembersUseCase:
    def execute(self, request_get, connection_module, paginate_fn):
        query = """
        SELECT id,
            banned,
            id_discord,
            id_guild_discord,
            id_user_discord,
            nick
        FROM member_discord;
    """

        with connection_module.cursor() as cursor:
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

        return paginate_fn(members, request_get.get("page")), 200
