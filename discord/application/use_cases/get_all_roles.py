class GetAllRolesUseCase:
    def execute(self, request_get, connection_module, paginate_fn):
        query = """
        SELECT id,
            active
        FROM role_discord;
    """

        with connection_module.cursor() as cursor:
            cursor.execute(query)
            roles = cursor.fetchall()

        roles = [{"id": role[0], "active": role[1]} for role in roles]

        return paginate_fn(roles, request_get.get("page")), 200
