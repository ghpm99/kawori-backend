class SocialAccountUnlinkUseCase:
    def execute(self, user, provider, social_account_model):
        provider = (provider or "").strip().lower()
        account = social_account_model.objects.filter(
            user=user, provider=provider
        ).first()
        if not account:
            return {"msg": "Conta social não encontrada."}, 404, None

        has_password_login = user.has_usable_password()
        social_count = social_account_model.objects.filter(user=user).count()
        if not has_password_login and social_count <= 1:
            return (
                {"msg": "Não é possível desvincular a única forma de acesso da conta."},
                400,
                None,
            )

        return {"msg": "Conta social desvinculada."}, 200, account
