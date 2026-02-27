import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.utils import timezone

from django.conf import settings

from authentication.models import PasswordResetToken


# Create your tests here.
class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        user = User.objects.create_user(
            username="test_auth",
            email="test@auth.com",
            password="user123",
            first_name="test",
            last_name="auth",
        )

        inactive = User.objects.create_user(
            username="user_inactive",
            email="test@active.com",
            password="user123",
            first_name="test",
            last_name="inactive",
        )
        inactive.is_active = False
        inactive.save()

        user_group, _ = Group.objects.get_or_create(name="user")
        user_group.user_set.add(user)
        user_group.user_set.add(inactive)

    def test_fail_signup_user(self):
        """Testa se falha o cadastro"""
        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data={"username": "test_user", "password": "user123"},
        )

        self.assertEqual(response.status_code, 400)
        response_json = json.loads(response.content)

        self.assertEqual(response_json["msg"], "Todos os campos são obrigatórios.")

    def test_success_signup_user(self):
        """Testa o sucesso no cadastro"""
        user_data = {
            "username": "test_user",
            "password": "user123",
            "email": "email@teste.com",
            "name": "test",
            "last_name": "user",
        }

        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data=user_data,
        )

        self.assertEqual(response.status_code, 200)
        response_json = json.loads(response.content)

        self.assertEqual(response_json["msg"], "Usuário criado com sucesso!")

    def test_success_login(self):
        """Testa obter tokens"""
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_auth", "password": "user123"},
        )

        self.assertEqual(response.status_code, 200)
        response_cookies = response.cookies

        access_token = response_cookies.get(settings.ACCESS_TOKEN_NAME)
        self.assertIsNotNone(access_token)

    def test_fail_login(self):
        """Testa falha no login"""
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        response_json = json.loads(response.content)

        self.assertEqual(
            response_json,
            {
                "errors": [
                    {"username": "Este campo é obrigatório"},
                    {"password": "Este campo é obrigatório"},
                ]
            },
        )

        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_user", "password": "user123"},
        )

        self.assertEqual(response.status_code, 404)
        response_json = json.loads(response.content)

        self.assertEqual(response_json, {"msg": "Dados incorretos."})

        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "user_inactive", "password": "user123"},
        )

        self.assertEqual(response.status_code, 404)
        response_json = json.loads(response.content)

        self.assertEqual(response_json, {"msg": "Dados incorretos."})

    def test_user_view(self):
        """Testa view de dados de usuario"""
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test_auth", "password": "user123"},
        )

        self.assertEqual(response.status_code, 200)

        cookies = response.cookies
        access_token = cookies.get(settings.ACCESS_TOKEN_NAME)

        self.assertIsNotNone(access_token)

        for key, morsel in cookies.items():
            self.client.cookies[key] = morsel.value

        response_user = self.client.get("/profile/")

        self.assertEqual(response_user.status_code, 200)

        response_user_json = json.loads(response_user.content)
        del response_user_json["id"]
        del response_user_json["last_login"]
        del response_user_json["date_joined"]

        self.assertDictEqual(
            response_user_json,
            {
                "name": "test auth",
                "username": "test_auth",
                "first_name": "test",
                "last_name": "auth",
                "email": "test@auth.com",
                "is_staff": False,
                "is_active": True,
                "is_superuser": False,
            },
        )


class PasswordResetRequestTestCase(TestCase):
    """Testes para POST /auth/password-reset/request/"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="reset_user",
            email="reset@test.com",
            password="OldPassword123!",
            first_name="Reset",
            last_name="User",
        )

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_success(self, mock_send):
        """Retorna 200 e dispara o email quando o e-mail existe"""
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "reset@test.com"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("msg", data)
        mock_send.assert_called_once()

        # Token deve ter sido criado no banco
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 1)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_email_case_insensitive(self, mock_send):
        """E-mail deve ser comparado sem distinção de maiúsculas"""
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "RESET@TEST.COM"},
        )

        self.assertEqual(response.status_code, 200)
        mock_send.assert_called_once()

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_nonexistent_email_returns_200(self, mock_send):
        """Retorna 200 genérico para e-mail inexistente (anti-enumeração)"""
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "naoexiste@test.com"},
        )

        self.assertEqual(response.status_code, 200)
        # Não deve ter enviado e-mail nem criado token
        mock_send.assert_not_called()
        self.assertEqual(PasswordResetToken.objects.count(), 0)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_inactive_user_returns_200(self, mock_send):
        """Usuário inativo é tratado como inexistente (anti-enumeração)"""
        inactive = User.objects.create_user(
            username="inactive_reset",
            email="inactive@test.com",
            password="pass123",
            is_active=False,
        )

        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "inactive@test.com"},
        )

        self.assertEqual(response.status_code, 200)
        mock_send.assert_not_called()

    def test_request_missing_email(self):
        """Retorna 400 quando o campo e-mail está ausente"""
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={},
        )

        self.assertEqual(response.status_code, 400)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_invalidates_previous_token(self, mock_send):
        """Nova solicitação invalida tokens anteriores do mesmo usuário"""
        # Primeira solicitação
        self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "reset@test.com"},
        )

        first_token = PasswordResetToken.objects.get(user=self.user)
        first_hash = first_token.token_hash

        # Segunda solicitação
        self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "reset@test.com"},
        )

        # Token anterior deve estar marcado como usado
        first_token.refresh_from_db()
        self.assertTrue(first_token.used)

        # Deve existir um novo token ativo
        active_tokens = PasswordResetToken.objects.filter(user=self.user, used=False)
        self.assertEqual(active_tokens.count(), 1)
        self.assertNotEqual(active_tokens.first().token_hash, first_hash)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_rate_limit_by_ip(self, mock_send):
        """Bloqueia após exceder o limite de tentativas por IP"""
        limit = PasswordResetToken.MAX_REQUESTS_PER_IP_PER_HOUR

        # Cria usuários distintos para não acionar o rate-limit por usuário
        users = []
        for i in range(limit):
            u = User.objects.create_user(
                username=f"rl_user_{i}",
                email=f"rl_{i}@test.com",
                password="pass123",
            )
            users.append(u)
            self.client.post(
                "/auth/password-reset/request/",
                content_type="application/json",
                data={"email": f"rl_{i}@test.com"},
            )

        # A próxima tentativa deve ser bloqueada
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "reset@test.com"},
        )

        self.assertEqual(response.status_code, 429)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_rate_limit_by_user(self, mock_send):
        """Retorna mensagem genérica após exceder o limite por usuário"""
        limit = PasswordResetToken.MAX_REQUESTS_PER_USER_PER_HOUR

        for _ in range(limit):
            self.client.post(
                "/auth/password-reset/request/",
                content_type="application/json",
                data={"email": "reset@test.com"},
            )

        # A próxima tentativa ainda retorna 200 (não revela o bloqueio)
        response = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data={"email": "reset@test.com"},
        )

        self.assertEqual(response.status_code, 200)
        # Mas o total de tokens não deve aumentar além do limite
        self.assertEqual(mock_send.call_count, limit)


class PasswordResetValidateTestCase(TestCase):
    """Testes para GET /auth/password-reset/validate/"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="validate_user",
            email="validate@test.com",
            password="OldPassword123!",
        )

    def test_validate_valid_token(self):
        """Token válido retorna valid=True"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")

        response = self.client.get(
            "/auth/password-reset/validate/",
            {"token": raw_token},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["valid"])

    def test_validate_nonexistent_token(self):
        """Token inexistente retorna 400"""
        response = self.client.get(
            "/auth/password-reset/validate/",
            {"token": "tokeninexistente"},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["valid"])

    def test_validate_expired_token(self):
        """Token expirado retorna 400"""
        raw_token = PasswordResetToken.generate_raw_token()
        token_hash = PasswordResetToken.hash_token(raw_token)
        PasswordResetToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            expires_at=timezone.now() - timedelta(minutes=1),  # já expirado
        )

        response = self.client.get(
            "/auth/password-reset/validate/",
            {"token": raw_token},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["valid"])

    def test_validate_used_token(self):
        """Token já utilizado retorna 400"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")
        token_obj = PasswordResetToken.objects.get(user=self.user)
        token_obj.consume("127.0.0.1")

        response = self.client.get(
            "/auth/password-reset/validate/",
            {"token": raw_token},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["valid"])

    def test_validate_missing_token(self):
        """Sem parâmetro token retorna 400"""
        response = self.client.get("/auth/password-reset/validate/")

        self.assertEqual(response.status_code, 400)


class PasswordResetConfirmTestCase(TestCase):
    """Testes para POST /auth/password-reset/confirm/"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="confirm_user",
            email="confirm@test.com",
            password="OldPassword123!",
        )

    def test_confirm_success(self):
        """Redefinição bem-sucedida retorna 200 e atualiza a senha"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "NewStrongPassword456!"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("msg", data)

        # Senha deve ter sido alterada
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword456!"))

        # Token deve estar marcado como usado
        token_obj = PasswordResetToken.objects.get(token_hash=PasswordResetToken.hash_token(raw_token))
        self.assertTrue(token_obj.used)
        self.assertIsNotNone(token_obj.ip_used)

    def test_confirm_invalid_token(self):
        """Token inválido retorna 400"""
        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": "tokenfalso", "new_password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, 400)

    def test_confirm_expired_token(self):
        """Token expirado retorna 400"""
        raw_token = PasswordResetToken.generate_raw_token()
        token_hash = PasswordResetToken.hash_token(raw_token)
        PasswordResetToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, 400)

    def test_confirm_used_token(self):
        """Token já utilizado retorna 400"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")
        token_obj = PasswordResetToken.objects.get(user=self.user)
        token_obj.consume("127.0.0.1")

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, 400)

    def test_confirm_weak_password(self):
        """Senha fraca é rejeitada pelas validações do Django"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "123"},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("msg", data)
        # Senha não deve ter sido alterada
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))

    def test_confirm_missing_fields(self):
        """Campos ausentes retornam 400"""
        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": "algumtoken"},
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"new_password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, 400)

    def test_confirm_token_not_reusable(self):
        """Token não pode ser usado duas vezes"""
        raw_token = PasswordResetToken.create_for_user(self.user, "127.0.0.1")

        # Primeiro uso — sucesso
        self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "NewPassword456!"},
        )

        # Segundo uso — deve falhar
        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "AnotherPassword789!"},
        )

        self.assertEqual(response.status_code, 400)
