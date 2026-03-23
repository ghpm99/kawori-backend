class VerifyEmailUseCase:
    def execute(
        self,
        raw_token,
        request,
        user_token_model,
        email_verification_model,
        transaction_module,
        timezone_module,
        get_client_ip_fn,
    ):
        token_hash = user_token_model.hash_token(raw_token)

        try:
            token_obj = user_token_model.objects.select_related("user").get(
                token_hash=token_hash,
                token_type=user_token_model.TOKEN_TYPE_EMAIL_VERIFICATION,
            )
        except user_token_model.DoesNotExist:
            return {"msg": "Token inválido ou expirado."}, 400

        if not token_obj.is_valid():
            return {"msg": "Token inválido ou expirado."}, 400

        user = token_obj.user

        with transaction_module.atomic():
            verification, _ = email_verification_model.objects.get_or_create(user=user)
            verification.is_verified = True
            verification.verified_at = timezone_module.now()
            verification.save(update_fields=["is_verified", "verified_at"])

            ip_address = get_client_ip_fn(request)
            token_obj.consume(ip_address)

        return {"msg": "Email verificado com sucesso."}, 200
