class SignoutUseCase:
    def execute(
        self,
        access_token_name,
        refresh_token_name,
        cookie_domain,
        refresh_path,
    ):
        delete_cookie_instructions = [
            {"key": access_token_name, "domain": cookie_domain},
            {"key": refresh_token_name, "path": refresh_path, "domain": cookie_domain},
            {"key": "lifetimetoken", "domain": cookie_domain},
        ]
        return {"msg": "Deslogou"}, 200, delete_cookie_instructions
