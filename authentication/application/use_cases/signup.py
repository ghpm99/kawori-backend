class SignupUseCase:
    def execute(
        self,
        payload,
        request,
        user_model,
        transaction_module,
        register_groups_fn,
        email_verification_model,
        get_client_ip_fn,
        user_token_model,
        send_verification_email_async_fn,
    ):
        required_fields = ["username", "password", "email", "name", "last_name"]
        for field in required_fields:
            if not payload.get(field):
                return {"msg": "Todos os campos são obrigatórios."}, 400

        username = payload["username"]
        password = payload["password"]
        email = payload["email"]
        name = payload["name"]
        last_name = payload["last_name"]

        username_exists = user_model.objects.filter(username=username).exists()
        if username_exists:
            return {"msg": "Usuário já cadastrado"}, 400

        email_exists = user_model.objects.filter(email=email).exists()
        if email_exists:
            return {"msg": "E-mail já cadastrado"}, 400

        with transaction_module.atomic():
            user = user_model.objects.create_user(
                username=username, password=password, email=email
            )
            user.first_name = name
            user.last_name = last_name
            user.save()

            register_groups_fn(user)

            try:
                from budget.services import create_default_budgets_for_user

                create_default_budgets_for_user(user)
            except Exception:  # nosec B110
                pass

            email_verification_model.objects.create(user=user)

        try:
            ip_address = get_client_ip_fn(request)
            raw_token = user_token_model.create_for_user(
                user,
                token_type=user_token_model.TOKEN_TYPE_EMAIL_VERIFICATION,
                ip_address=ip_address,
            )
            send_verification_email_async_fn(user, raw_token)
        except Exception:  # nosec B110
            pass

        return {"msg": "Usuário criado com sucesso!"}, 200
