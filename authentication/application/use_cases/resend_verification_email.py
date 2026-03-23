class ResendVerificationEmailUseCase:
    def execute(
        self,
        user,
        request,
        email_verification_model,
        user_token_model,
        get_client_ip_fn,
        send_verification_email_async_fn,
    ):
        try:
            verification = email_verification_model.objects.get(user=user)
        except email_verification_model.DoesNotExist:
            verification = email_verification_model.objects.create(user=user)

        if verification.is_verified:
            return {"msg": "Email já verificado."}, 200

        if user_token_model.is_rate_limited_by_user(
            user, user_token_model.TOKEN_TYPE_EMAIL_VERIFICATION
        ):
            return {"msg": "Muitas tentativas. Tente novamente mais tarde."}, 429

        ip_address = get_client_ip_fn(request)
        raw_token = user_token_model.create_for_user(
            user,
            token_type=user_token_model.TOKEN_TYPE_EMAIL_VERIFICATION,
            ip_address=ip_address,
        )
        send_verification_email_async_fn(user, raw_token)

        return {"msg": "Email de verificação reenviado."}, 200
