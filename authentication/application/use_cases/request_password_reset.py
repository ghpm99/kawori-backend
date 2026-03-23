class RequestPasswordResetUseCase:
    def execute(
        self,
        email,
        request,
        user_model,
        user_token_model,
        get_client_ip_fn,
        send_password_reset_email_async_fn,
        reset_generic_msg,
    ):
        ip_address = get_client_ip_fn(request)

        if user_token_model.is_rate_limited_by_ip(
            ip_address, user_token_model.TOKEN_TYPE_PASSWORD_RESET
        ):
            return {"msg": "Muitas tentativas. Tente novamente mais tarde."}, 429

        try:
            user = user_model.objects.get(email__iexact=email, is_active=True)
        except user_model.DoesNotExist:
            return {"msg": reset_generic_msg}, 200

        if user_token_model.is_rate_limited_by_user(
            user, user_token_model.TOKEN_TYPE_PASSWORD_RESET
        ):
            return {"msg": reset_generic_msg}, 200

        raw_token = user_token_model.create_for_user(
            user,
            token_type=user_token_model.TOKEN_TYPE_PASSWORD_RESET,
            ip_address=ip_address,
        )
        send_password_reset_email_async_fn(user, raw_token)

        return {"msg": reset_generic_msg}, 200
