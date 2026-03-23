class RefreshTokenUseCase:
    def execute(self, refresh_token_cookie, refresh_token_cls):
        if refresh_token_cookie is None:
            return {"msg": "Token não encontrado"}, 403, None

        try:
            refresh_token = refresh_token_cls(refresh_token_cookie)
            refresh_token.verify()
            refresh_token.verify_token_type()

            access_token = refresh_token.access_token
            return {"msg": "Token válido"}, 200, access_token
        except Exception as exc:
            return {"error": str(exc), "valid": False}, 403, None
