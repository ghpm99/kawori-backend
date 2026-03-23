class ConfirmPasswordResetUseCase:
    def execute(
        self,
        raw_token,
        new_password,
        request,
        user_token_model,
        validate_password_fn,
        validation_error_cls,
        transaction_module,
        get_client_ip_fn,
    ):
        token_hash = user_token_model.hash_token(raw_token)

        try:
            token_obj = user_token_model.objects.select_related("user").get(
                token_hash=token_hash,
                token_type=user_token_model.TOKEN_TYPE_PASSWORD_RESET,
            )
        except user_token_model.DoesNotExist:
            return {"msg": "Token inválido ou expirado."}, 400

        if not token_obj.is_valid():
            return {"msg": "Token inválido ou expirado."}, 400

        user = token_obj.user

        try:
            validate_password_fn(new_password, user)
        except validation_error_cls as exc:
            return {"msg": list(exc.messages)}, 400

        with transaction_module.atomic():
            user.set_password(new_password)
            user.save(update_fields=["password"])

            ip_address = get_client_ip_fn(request)
            token_obj.consume(ip_address)

        return {"msg": "Senha redefinida com sucesso."}, 200
