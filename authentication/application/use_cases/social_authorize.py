from http import HTTPStatus


class SocialAuthorizeUseCase:
    def execute(
        self,
        request,
        provider,
        get_social_provider_config_fn,
        social_oauth_error_cls,
        get_current_user_from_cookie_fn,
        social_auth_state_model,
        social_auth_state_expiration_minutes,
        reverse_fn,
        build_social_authorize_url_fn,
    ):
        try:
            provider_config = get_social_provider_config_fn(provider)
        except social_oauth_error_cls as exc:
            return {"msg": exc.message}, exc.status_code

        current_user = get_current_user_from_cookie_fn(request)
        requested_mode = (request.GET.get("mode") or "").strip().lower()
        mode = (
            social_auth_state_model.MODE_LINK
            if requested_mode == social_auth_state_model.MODE_LINK
            else social_auth_state_model.MODE_LOGIN
        )
        if mode == social_auth_state_model.MODE_LINK and not current_user:
            return {"msg": "Usuário precisa estar autenticado para vincular."}, int(
                HTTPStatus.UNAUTHORIZED
            )

        frontend_redirect_uri = (request.GET.get("frontend_redirect_uri") or "").strip()
        redirect_uri = request.build_absolute_uri(
            reverse_fn("auth_social_callback", kwargs={"provider": provider})
        )
        raw_state = social_auth_state_model.create_for_provider(
            provider=provider,
            mode=mode,
            user=current_user if mode == social_auth_state_model.MODE_LINK else None,
            frontend_redirect_uri=frontend_redirect_uri,
            expiration_minutes=social_auth_state_expiration_minutes,
        )
        authorize_url = build_social_authorize_url_fn(
            provider_config, raw_state, redirect_uri
        )

        return {"provider": provider, "mode": mode, "authorize_url": authorize_url}, 200
