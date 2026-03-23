class GetAllGuildsUseCase:
    def execute(self, request_get, connection_module, paginate_fn):
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

        with connection_module.cursor() as cursor:
            cursor.execute(query)
            guilds = cursor.fetchall()

        guilds = [
            {
                "id": guild[0],
                "active": guild[1],
                "block": guild[2],
                "id_discord": guild[3],
                "id_owner": guild[4],
                "last_message": guild[5],
                "name": guild[6],
            }
            for guild in guilds
        ]

        return paginate_fn(guilds, request_get.get("page")), 200
