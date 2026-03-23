class VerifyTokenUseCase:
    def execute(self, access_token_cookie, access_token_cls):
        if access_token_cookie is None:
            return {"msg": "Token não encontrado"}, 400, False

        try:
            token = access_token_cls(access_token_cookie)
            token.verify()
            token.verify_token_type()
            return {"msg": "Token válido"}, 200, False
        except Exception as exc:
            return {"error": str(exc), "valid": False}, 401, True
