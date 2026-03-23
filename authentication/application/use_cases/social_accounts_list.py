class SocialAccountsListUseCase:
    def execute(self, user, social_account_model):
        accounts = social_account_model.objects.filter(user=user).order_by("provider")
        payload = []
        for account in accounts:
            payload.append(
                {
                    "provider": account.provider,
                    "email": account.email,
                    "is_email_verified": account.is_email_verified,
                    "full_name": account.full_name,
                    "avatar_url": account.avatar_url,
                    "linked_at": account.linked_at.isoformat(),
                    "last_login_at": (
                        account.last_login_at.isoformat() if account.last_login_at else None
                    ),
                }
            )
        return {"accounts": payload}, 200
