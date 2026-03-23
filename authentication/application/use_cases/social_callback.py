class SocialCallbackUseCase:
    def execute(
        self,
        request,
        provider,
        social_oauth_error_cls,
        get_social_provider_config_fn,
        json_response_cls,
        http_status_module,
        social_auth_state_model,
        reverse_fn,
        exchange_social_code_for_token_fn,
        fetch_social_profile_fn,
        redirect_or_json_fn,
        transaction_module,
        social_account_model,
        user_model,
        create_user_from_social_profile_fn,
        timezone_module,
        email_verification_model,
        build_auth_response_fn,
        http_response_redirect_cls,
    ):
        code = (request.GET.get("code") or "").strip()
        state_raw = (request.GET.get("state") or "").strip()
        provider_error = (request.GET.get("error") or "").strip()

        try:
            provider_config = get_social_provider_config_fn(provider)
        except social_oauth_error_cls as exc:
            return json_response_cls({"msg": exc.message}, status=exc.status_code)

        if provider_error:
            return json_response_cls(
                {"msg": f"Erro retornado pelo provedor: {provider_error}"},
                status=http_status_module.BAD_REQUEST,
            )

        if not code or not state_raw:
            return json_response_cls(
                {"msg": "Parâmetros OAuth inválidos."},
                status=http_status_module.BAD_REQUEST,
            )

        state_hash = social_auth_state_model.hash_state(state_raw)
        state_obj = (
            social_auth_state_model.objects.select_related("user")
            .filter(provider=provider, state_hash=state_hash)
            .first()
        )
        if not state_obj or not state_obj.is_valid():
            return json_response_cls(
                {"msg": "Estado OAuth inválido ou expirado."},
                status=http_status_module.BAD_REQUEST,
            )

        try:
            redirect_uri = request.build_absolute_uri(
                reverse_fn("auth_social_callback", kwargs={"provider": provider})
            )
            token_data = exchange_social_code_for_token_fn(provider_config, code, redirect_uri)
            profile = fetch_social_profile_fn(provider_config, token_data)
        except social_oauth_error_cls as exc:
            state_obj.consume()
            return redirect_or_json_fn(
                state_obj,
                {"status": "error", "msg": exc.message},
                status_code=exc.status_code,
            )
        except Exception:
            state_obj.consume()
            return redirect_or_json_fn(
                state_obj,
                {"status": "error", "msg": "Falha ao concluir login social."},
                status_code=400,
            )

        provider_user_id = (profile.get("provider_user_id") or "").strip()
        if not provider_user_id:
            state_obj.consume()
            return redirect_or_json_fn(
                state_obj,
                {"status": "error", "msg": "Perfil social sem identificador único."},
                status_code=400,
            )

        with transaction_module.atomic():
            social_account = (
                social_account_model.objects.select_related("user")
                .filter(provider=provider, provider_user_id=provider_user_id)
                .first()
            )

            email = (profile.get("email") or "").strip().lower()
            is_new_user = False
            linked_existing_user = False

            if state_obj.mode == social_auth_state_model.MODE_LINK:
                if not state_obj.user or not state_obj.user.is_active:
                    state_obj.consume()
                    return redirect_or_json_fn(
                        state_obj,
                        {
                            "status": "error",
                            "msg": "Usuário autenticado inválido para vínculo.",
                        },
                        status_code=http_status_module.FORBIDDEN,
                    )

                target_user = state_obj.user
                if social_account and social_account.user_id != target_user.id:
                    state_obj.consume()
                    return redirect_or_json_fn(
                        state_obj,
                        {
                            "status": "error",
                            "msg": "Esta conta social já está vinculada a outro usuário.",
                        },
                        status_code=http_status_module.CONFLICT,
                    )
            else:
                if social_account:
                    target_user = social_account.user
                    if not target_user.is_active:
                        state_obj.consume()
                        return redirect_or_json_fn(
                            state_obj,
                            {"status": "error", "msg": "Usuário vinculado está inativo."},
                            status_code=http_status_module.FORBIDDEN,
                        )
                else:
                    target_user = None
                    if email:
                        target_user = user_model.objects.filter(email__iexact=email).first()
                        linked_existing_user = bool(target_user)

                    if target_user is None:
                        target_user = create_user_from_social_profile_fn(profile, provider)
                        is_new_user = True

            social_defaults = {
                "email": email,
                "is_email_verified": bool(profile.get("is_email_verified")),
                "full_name": profile.get("full_name", "") or "",
                "avatar_url": profile.get("avatar_url", "") or "",
                "profile_data": profile.get("raw", {}),
                "last_login_at": timezone_module.now(),
            }

            user_provider_link = social_account_model.objects.filter(
                user=target_user, provider=provider
            ).first()
            if (
                user_provider_link
                and user_provider_link.provider_user_id != provider_user_id
            ):
                state_obj.consume()
                return redirect_or_json_fn(
                    state_obj,
                    {
                        "status": "error",
                        "msg": "Usuário já possui outra conta vinculada neste provedor.",
                    },
                    status_code=http_status_module.CONFLICT,
                )

            if social_account:
                for key, value in social_defaults.items():
                    setattr(social_account, key, value)
                social_account.user = target_user
                social_account.save()
            else:
                social_account_model.objects.create(
                    user=target_user,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    **social_defaults,
                )

            if (
                social_defaults["is_email_verified"]
                and target_user.email
                and target_user.email.lower() == email
            ):
                verification, _ = email_verification_model.objects.get_or_create(
                    user=target_user
                )
                if not verification.is_verified:
                    verification.is_verified = True
                    verification.verified_at = timezone_module.now()
                    verification.save(update_fields=["is_verified", "verified_at"])

            state_obj.consume()

        response_payload = {
            "status": "success",
            "provider": provider,
            "mode": state_obj.mode,
            "is_new_user": is_new_user,
            "linked_existing_user": linked_existing_user,
            "msg": (
                "Conta social vinculada com sucesso."
                if state_obj.mode == social_auth_state_model.MODE_LINK
                else "Login social concluído."
            ),
        }

        if state_obj.mode == social_auth_state_model.MODE_LINK:
            return redirect_or_json_fn(state_obj, response_payload)

        response = redirect_or_json_fn(state_obj, response_payload)
        if isinstance(response, http_response_redirect_cls):
            cookie_response = build_auth_response_fn(target_user, payload={})
            for cookie_key in cookie_response.cookies:
                response.cookies[cookie_key] = cookie_response.cookies[cookie_key]
            return response

        return build_auth_response_fn(target_user, payload=response_payload)
