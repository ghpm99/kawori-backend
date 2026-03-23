class ValidateResetTokenUseCase:
    def execute(self, raw_token, user_token_model):
        token_hash = user_token_model.hash_token(raw_token)

        try:
            token_obj = user_token_model.objects.get(
                token_hash=token_hash,
                token_type=user_token_model.TOKEN_TYPE_PASSWORD_RESET,
            )
        except user_token_model.DoesNotExist:
            return {"valid": False, "msg": "Token inválido ou expirado."}, 400

        if not token_obj.is_valid():
            return {"valid": False, "msg": "Token inválido ou expirado."}, 400

        return {"valid": True}, 200
