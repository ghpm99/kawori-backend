class GetAllUsersUseCase:
    def execute(self, request_get, connection_module, paginate_fn):
        query = """
        SELECT id,
            banned,
            discriminator,
            id_discord,
            last_message,
            name
        FROM user_discord;
    """

        with connection_module.cursor() as cursor:
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

        return paginate_fn(users, request_get.get("page")), 200
