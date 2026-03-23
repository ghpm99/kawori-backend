class ObtainTokenPairUseCase:
    def execute(self, payload, authenticate_fn):
        err = []

        if not payload.get("username"):
            err.append({"username": "Este campo é obrigatório"})
        if not payload.get("password"):
            err.append({"password": "Este campo é obrigatório"})
        if err:
            return {"errors": err}, 400, None

        user = authenticate_fn(
            username=payload.get("username"),
            password=payload.get("password"),
        )

        if not user:
            return {"msg": "Dados incorretos."}, 404, None
        if not user.is_active:
            return {"msg": "Este usuário não está ativo."}, 403, None

        return {}, 200, user
