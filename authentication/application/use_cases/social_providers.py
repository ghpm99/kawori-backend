class SocialProvidersUseCase:
    def execute(self, list_enabled_social_providers_fn):
        return {"providers": list_enabled_social_providers_fn()}, 200
