import json
import inspect
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from authentication.models import EmailVerification, SocialAccount, UserToken
from authentication import views
from authentication import utils as auth_utils


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

    @patch("authentication.views.send_verification_email_async")
    def test_success_signup_user(self, mock_send_verification):
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
        self.assertEqual(
            UserToken.objects.filter(
                user=self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET
            ).count(),
            1,
        )

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
        self.assertEqual(UserToken.objects.count(), 0)

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

        first_token = UserToken.objects.get(
            user=self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET
        )
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
        active_tokens = UserToken.objects.filter(
            user=self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, used=False
        )
        self.assertEqual(active_tokens.count(), 1)
        self.assertNotEqual(active_tokens.first().token_hash, first_hash)

    @patch("authentication.views.send_password_reset_email_async")
    def test_request_rate_limit_by_ip(self, mock_send):
        """Bloqueia após exceder o limite de tentativas por IP"""
        limit = UserToken.MAX_REQUESTS_PER_IP_PER_HOUR

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
        limit = UserToken.MAX_REQUESTS_PER_USER_PER_HOUR

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
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )

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
        raw_token = UserToken.generate_raw_token()
        token_hash = UserToken.hash_token(raw_token)
        UserToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET,
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
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )
        token_obj = UserToken.objects.get(user=self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET)
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
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )

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
        token_obj = UserToken.objects.get(token_hash=UserToken.hash_token(raw_token))
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
        raw_token = UserToken.generate_raw_token()
        token_hash = UserToken.hash_token(raw_token)
        UserToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET,
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
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )
        token_obj = UserToken.objects.get(user=self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET)
        token_obj.consume("127.0.0.1")

        response = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data={"token": raw_token, "new_password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, 400)

    def test_confirm_weak_password(self):
        """Senha fraca é rejeitada pelas validações do Django"""
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )

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
        raw_token = UserToken.create_for_user(
            self.user, token_type=UserToken.TOKEN_TYPE_PASSWORD_RESET, ip_address="127.0.0.1"
        )

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


class EmailVerificationSignupTestCase(TestCase):
    """Testes para verificação de email no signup"""

    def setUp(self):
        self.client = Client()
        Group.objects.get_or_create(name="user")
        Group.objects.get_or_create(name="blackdesert")
        Group.objects.get_or_create(name="financial")

    @patch("authentication.views.send_verification_email_async")
    def test_signup_creates_email_verification(self, mock_send):
        """Signup cria EmailVerification com is_verified=False"""
        user_data = {
            "username": "new_user",
            "password": "user123",
            "email": "new@test.com",
            "name": "New",
            "last_name": "User",
        }

        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data=user_data,
        )

        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username="new_user")
        verification = EmailVerification.objects.get(user=user)
        self.assertFalse(verification.is_verified)
        self.assertIsNone(verification.verified_at)

    @patch("authentication.views.send_verification_email_async")
    def test_signup_creates_verification_token(self, mock_send):
        """Signup cria token de verificação e envia email"""
        user_data = {
            "username": "token_user",
            "password": "user123",
            "email": "token@test.com",
            "name": "Token",
            "last_name": "User",
        }

        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data=user_data,
        )

        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username="token_user")
        token = UserToken.objects.get(
            user=user, token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION
        )
        self.assertFalse(token.used)
        mock_send.assert_called_once()


class EmailVerificationVerifyTestCase(TestCase):
    """Testes para POST /auth/email/verify/"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="verify_user",
            email="verify@test.com",
            password="Password123!",
        )
        EmailVerification.objects.create(user=self.user)

    def test_verify_email_success(self):
        """Token válido verifica email com sucesso"""
        raw_token = UserToken.create_for_user(
            self.user,
            token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION,
            ip_address="127.0.0.1",
        )

        response = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data={"token": raw_token},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["msg"], "Email verificado com sucesso.")

        verification = EmailVerification.objects.get(user=self.user)
        self.assertTrue(verification.is_verified)
        self.assertIsNotNone(verification.verified_at)

        # Token deve estar consumido
        token_obj = UserToken.objects.get(token_hash=UserToken.hash_token(raw_token))
        self.assertTrue(token_obj.used)

    def test_verify_email_invalid_token(self):
        """Token inválido retorna erro"""
        response = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data={"token": "tokenfalso"},
        )

        self.assertEqual(response.status_code, 400)

    def test_verify_email_expired_token(self):
        """Token expirado retorna erro"""
        raw_token = UserToken.generate_raw_token()
        token_hash = UserToken.hash_token(raw_token)
        UserToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data={"token": raw_token},
        )

        self.assertEqual(response.status_code, 400)

    def test_verify_email_used_token(self):
        """Token já usado retorna erro"""
        raw_token = UserToken.create_for_user(
            self.user,
            token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION,
            ip_address="127.0.0.1",
        )
        token_obj = UserToken.objects.get(
            user=self.user, token_type=UserToken.TOKEN_TYPE_EMAIL_VERIFICATION, used=False
        )
        token_obj.consume("127.0.0.1")

        response = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data={"token": raw_token},
        )

        self.assertEqual(response.status_code, 400)

    def test_verify_email_missing_token(self):
        """Token ausente retorna erro"""
        response = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data={},
        )

        self.assertEqual(response.status_code, 400)


class EmailVerificationResendTestCase(TestCase):
    """Testes para POST /auth/email/resend-verification/"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="resend_user",
            email="resend@test.com",
            password="Password123!",
        )
        user_group, _ = Group.objects.get_or_create(name="user")
        user_group.user_set.add(self.user)
        EmailVerification.objects.create(user=self.user)

    def _login(self):
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "resend_user", "password": "Password123!"},
        )
        for key, morsel in response.cookies.items():
            self.client.cookies[key] = morsel.value

    @patch("authentication.views.send_verification_email_async")
    def test_resend_success(self, mock_send):
        """Reenvio funciona para não-verificados"""
        self._login()

        response = self.client.post("/auth/email/resend-verification/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["msg"], "Email de verificação reenviado.")
        mock_send.assert_called_once()

    @patch("authentication.views.send_verification_email_async")
    def test_resend_already_verified(self, mock_send):
        """Reenvio retorna mensagem quando já verificado"""
        self._login()

        verification = EmailVerification.objects.get(user=self.user)
        verification.is_verified = True
        verification.verified_at = timezone.now()
        verification.save()

        response = self.client.post("/auth/email/resend-verification/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["msg"], "Email já verificado.")
        mock_send.assert_not_called()

    def test_resend_requires_authentication(self):
        """Reenvio requer autenticação"""
        response = self.client.post("/auth/email/resend-verification/")

        self.assertEqual(response.status_code, 401)

    @patch("authentication.views.send_verification_email_async")
    def test_resend_rate_limited(self, mock_send):
        """Reenvio é bloqueado após exceder limite"""
        self._login()

        limit = UserToken.MAX_REQUESTS_PER_USER_PER_HOUR
        for _ in range(limit):
            self.client.post("/auth/email/resend-verification/")

        response = self.client.post("/auth/email/resend-verification/")

        self.assertEqual(response.status_code, 429)
        data = json.loads(response.content)
        self.assertEqual(data["msg"], "Muitas tentativas. Tente novamente mais tarde.")


class AuthenticationViewsRegressionExtraTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.rf = RequestFactory()
        self.active_user = User.objects.create_user(
            username="active_extra",
            email="active_extra@test.com",
            password="StrongPass123!",
        )
        self.inactive_user = User.objects.create_user(
            username="inactive_extra",
            email="inactive_extra@test.com",
            password="StrongPass123!",
            is_active=False,
        )
        user_group, _ = Group.objects.get_or_create(name="user")
        user_group.user_set.add(self.active_user)

    def _post_unwrapped(self, fn, data=None, cookies=None):
        request = self.rf.post("/", data=json.dumps(data or {}), content_type="application/json")
        for key, value in (cookies or {}).items():
            request.COOKIES[key] = value
        return inspect.unwrap(fn)(request)

    def test_obtain_token_pair_inactive_user_branch(self):
        with patch("authentication.views.authenticate", return_value=self.inactive_user):
            response = self._post_unwrapped(views.obtain_token_pair, {"username": "x", "password": "y"})

        self.assertEqual(response.status_code, 403)

    def test_obtain_token_pair_updates_existing_last_login(self):
        self.active_user.last_login = timezone.now() - timedelta(days=1)
        self.active_user.save(update_fields=["last_login"])

        with patch("authentication.views.authenticate", return_value=self.active_user):
            response = self._post_unwrapped(views.obtain_token_pair, {"username": "x", "password": "y"})

        self.assertEqual(response.status_code, 200)
        self.active_user.refresh_from_db()
        self.assertIsNotNone(self.active_user.last_login)

    def test_signout_verify_and_refresh_token_branches(self):
        signout = self.client.get("/auth/signout")
        self.assertEqual(signout.status_code, 200)
        self.assertIn(settings.ACCESS_TOKEN_NAME, signout.cookies)
        self.assertIn(settings.REFRESH_TOKEN_NAME, signout.cookies)
        self.assertIn("lifetimetoken", signout.cookies)

        missing_verify = self._post_unwrapped(views.verify_token, {})
        self.assertEqual(missing_verify.status_code, 400)

        valid_access = str(AccessToken.for_user(self.active_user))
        valid_verify = self._post_unwrapped(
            views.verify_token,
            {},
            cookies={settings.ACCESS_TOKEN_NAME: valid_access},
        )
        self.assertEqual(valid_verify.status_code, 200)

        invalid_verify = self._post_unwrapped(
            views.verify_token,
            {},
            cookies={settings.ACCESS_TOKEN_NAME: "invalid.token.value"},
        )
        self.assertEqual(invalid_verify.status_code, 401)

        missing_refresh = self._post_unwrapped(views.refresh_token, {})
        self.assertEqual(missing_refresh.status_code, 403)

        valid_refresh = str(RefreshToken.for_user(self.active_user))
        refresh_ok = self._post_unwrapped(
            views.refresh_token,
            {},
            cookies={settings.REFRESH_TOKEN_NAME: valid_refresh},
        )
        self.assertEqual(refresh_ok.status_code, 200)
        self.assertIn(settings.ACCESS_TOKEN_NAME, refresh_ok.cookies)

        refresh_invalid = self._post_unwrapped(
            views.refresh_token,
            {},
            cookies={settings.REFRESH_TOKEN_NAME: "invalid.token.value"},
        )
        self.assertEqual(refresh_invalid.status_code, 403)

    def test_signup_duplicate_and_optional_failures_and_csrf(self):
        User.objects.create_user(username="dup_user", email="dup@test.com", password="x")

        duplicate_username = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data={
                "username": "dup_user",
                "password": "x",
                "email": "newdup@test.com",
                "name": "Dup",
                "last_name": "User",
            },
        )
        self.assertEqual(duplicate_username.status_code, 400)

        duplicate_email = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data={
                "username": "newdup",
                "password": "x",
                "email": "dup@test.com",
                "name": "Dup",
                "last_name": "Email",
            },
        )
        self.assertEqual(duplicate_email.status_code, 400)

        with patch("budget.services.create_default_budgets_for_user", side_effect=Exception("budget-fail")), patch(
            "authentication.views.UserToken.create_for_user", side_effect=Exception("token-fail")
        ):
            optional_fail = self.client.post(
                "/auth/signup",
                content_type="application/json",
                data={
                    "username": "optional_fail_user",
                    "password": "x",
                    "email": "optional_fail@test.com",
                    "name": "Optional",
                    "last_name": "Fail",
                },
            )
        self.assertEqual(optional_fail.status_code, 200)

        csrf_response = self.client.get("/auth/csrf/")
        self.assertEqual(csrf_response.status_code, 200)

    def test_invalid_json_and_resend_without_existing_verification(self):
        invalid_reset = self.client.post(
            "/auth/password-reset/request/",
            content_type="application/json",
            data="{",
        )
        self.assertEqual(invalid_reset.status_code, 400)

        invalid_confirm = self.client.post(
            "/auth/password-reset/confirm/",
            content_type="application/json",
            data="{",
        )
        self.assertEqual(invalid_confirm.status_code, 400)

        invalid_verify_email = self.client.post(
            "/auth/email/verify/",
            content_type="application/json",
            data="{",
        )
        self.assertEqual(invalid_verify_email.status_code, 400)

        no_verif_user = User.objects.create_user(
            username="resend_no_verif",
            email="resend_no_verif@test.com",
            password="StrongPass123!",
        )
        user_group = Group.objects.get(name="user")
        user_group.user_set.add(no_verif_user)

        login = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "resend_no_verif", "password": "StrongPass123!"},
        )
        for key, morsel in login.cookies.items():
            self.client.cookies[key] = morsel.value

        with patch("authentication.views.send_verification_email_async"):
            resend = self.client.post("/auth/email/resend-verification/")

        self.assertEqual(resend.status_code, 200)
        self.assertTrue(EmailVerification.objects.filter(user=no_verif_user).exists())


class SocialAuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="social_existing",
            email="social_existing@test.com",
            password="Password123!",
            first_name="Social",
            last_name="Existing",
        )
        user_group, _ = Group.objects.get_or_create(name="user")
        user_group.user_set.add(self.user)

        self.social_settings = {
            "google": {"client_id": "id", "client_secret": "secret"},
            "discord": {"client_id": "", "client_secret": ""},
            "github": {"client_id": "", "client_secret": ""},
            "facebook": {"client_id": "", "client_secret": ""},
            "microsoft": {"client_id": "", "client_secret": ""},
        }

    def _extract_state(self, authorize_url: str) -> str:
        marker = "state="
        return authorize_url.split(marker, 1)[1].split("&", 1)[0]

    def _login_user(self):
        response = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "social_existing", "password": "Password123!"},
        )
        for key, morsel in response.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_social_providers_only_lists_enabled(self):
        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            response = self.client.get("/auth/social/providers/")
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(len(body["providers"]), 1)
        self.assertEqual(body["providers"][0]["provider"], "google")

    def test_social_login_links_existing_user_by_email(self):
        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            authorize = self.client.get("/auth/social/google/authorize/")
        state = self._extract_state(json.loads(authorize.content)["authorize_url"])

        with patch("authentication.views.exchange_social_code_for_token", return_value={"access_token": "abc"}), patch(
            "authentication.views.fetch_social_profile",
            return_value={
                "provider_user_id": "google-1",
                "email": "social_existing@test.com",
                "is_email_verified": True,
                "full_name": "Social Existing",
                "avatar_url": "http://avatar",
                "raw": {"sub": "google-1"},
            },
        ):
            with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
                callback = self.client.get(f"/auth/social/google/callback/?code=code123&state={state}")

        self.assertEqual(callback.status_code, 200)
        body = json.loads(callback.content)
        self.assertFalse(body["is_new_user"])
        self.assertTrue(body["linked_existing_user"])
        self.assertTrue(SocialAccount.objects.filter(user=self.user, provider="google").exists())
        self.assertIn(settings.ACCESS_TOKEN_NAME, callback.cookies)

    def test_social_login_creates_new_user_when_email_does_not_exist(self):
        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            authorize = self.client.get("/auth/social/google/authorize/")
        state = self._extract_state(json.loads(authorize.content)["authorize_url"])

        with patch("authentication.views.exchange_social_code_for_token", return_value={"access_token": "abc"}), patch(
            "authentication.views.fetch_social_profile",
            return_value={
                "provider_user_id": "google-2",
                "email": "new_social@test.com",
                "is_email_verified": True,
                "full_name": "New Social",
                "avatar_url": "http://avatar",
                "raw": {"sub": "google-2"},
            },
        ):
            with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
                callback = self.client.get(f"/auth/social/google/callback/?code=code123&state={state}")

        self.assertEqual(callback.status_code, 200)
        body = json.loads(callback.content)
        self.assertTrue(body["is_new_user"])
        created_user = User.objects.get(email="new_social@test.com")
        self.assertTrue(SocialAccount.objects.filter(user=created_user, provider="google").exists())
        self.assertTrue(EmailVerification.objects.get(user=created_user).is_verified)

    def test_social_link_logged_user_even_with_different_email(self):
        self._login_user()

        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            authorize = self.client.get("/auth/social/google/authorize/?mode=link")
        state = self._extract_state(json.loads(authorize.content)["authorize_url"])

        with patch("authentication.views.exchange_social_code_for_token", return_value={"access_token": "abc"}), patch(
            "authentication.views.fetch_social_profile",
            return_value={
                "provider_user_id": "google-3",
                "email": "other_email@test.com",
                "is_email_verified": True,
                "full_name": "Other Name",
                "avatar_url": "http://avatar",
                "raw": {"sub": "google-3"},
            },
        ):
            with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
                callback = self.client.get(f"/auth/social/google/callback/?code=code123&state={state}")

        self.assertEqual(callback.status_code, 200)
        body = json.loads(callback.content)
        self.assertEqual(body["mode"], "link")
        social = SocialAccount.objects.get(provider="google", provider_user_id="google-3")
        self.assertEqual(social.user_id, self.user.id)

    def test_social_link_conflict_when_already_linked_to_other_user(self):
        other_user = User.objects.create_user(
            username="other_social_user",
            email="other_social_user@test.com",
            password="Password123!",
        )
        Group.objects.get(name="user").user_set.add(other_user)
        SocialAccount.objects.create(
            user=other_user,
            provider="google",
            provider_user_id="google-conflict",
            email="other_social_user@test.com",
        )

        self._login_user()
        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            authorize = self.client.get("/auth/social/google/authorize/?mode=link")
        state = self._extract_state(json.loads(authorize.content)["authorize_url"])

        with patch("authentication.views.exchange_social_code_for_token", return_value={"access_token": "abc"}), patch(
            "authentication.views.fetch_social_profile",
            return_value={
                "provider_user_id": "google-conflict",
                "email": "whatever@test.com",
                "is_email_verified": True,
                "full_name": "Any Name",
                "avatar_url": "http://avatar",
                "raw": {"sub": "google-conflict"},
            },
        ):
            with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
                callback = self.client.get(f"/auth/social/google/callback/?code=code123&state={state}")

        self.assertEqual(callback.status_code, 409)

    def test_social_accounts_list_and_unlink(self):
        self._login_user()
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            provider_user_id="google-9",
            email="social_existing@test.com",
        )

        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            list_response = self.client.get("/auth/social/accounts/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(json.loads(list_response.content)["accounts"]), 1)

        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            unlink_response = self.client.post("/auth/social/accounts/google/unlink/")
        self.assertEqual(unlink_response.status_code, 200)
        self.assertFalse(SocialAccount.objects.filter(user=self.user, provider="google").exists())

    def test_social_unlink_prevents_orphan_access(self):
        passwordless = User.objects.create_user(username="passwordless_user", email="passwordless@test.com", password=None)
        passwordless.set_unusable_password()
        passwordless.save(update_fields=["password"])
        Group.objects.get(name="user").user_set.add(passwordless)

        SocialAccount.objects.create(
            user=passwordless,
            provider="google",
            provider_user_id="google-passwordless",
            email="passwordless@test.com",
        )

        login = self.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "social_existing", "password": "Password123!"},
        )
        for key, morsel in login.cookies.items():
            self.client.cookies[key] = morsel.value

        # troca usuário autenticado para o passwordless via token manual
        token = str(AccessToken.for_user(passwordless))
        self.client.cookies[settings.ACCESS_TOKEN_NAME] = token

        with override_settings(SOCIAL_AUTH_PROVIDERS=self.social_settings):
            response = self.client.post("/auth/social/accounts/google/unlink/")
        self.assertEqual(response.status_code, 400)


class AuthenticationUtilsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="utils_user",
            email="utils@test.com",
            password="StrongPass123!",
        )

    def test_get_token_register_groups_and_get_client_ip(self):
        Group.objects.get_or_create(name="user")
        Group.objects.get_or_create(name="blackdesert")
        Group.objects.get_or_create(name="financial")

        tokens = auth_utils.get_token(self.user)
        self.assertIn("refresh", tokens)
        self.assertIn("access", tokens)

        auth_utils.register_groups(self.user)
        self.assertTrue(self.user.groups.filter(name="user").exists())
        self.assertTrue(self.user.groups.filter(name="blackdesert").exists())
        self.assertTrue(self.user.groups.filter(name="financial").exists())

        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="10.0.0.1, 10.0.0.2", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(auth_utils.get_client_ip(request), "10.0.0.1")

        request_no_proxy = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(auth_utils.get_client_ip(request_no_proxy), "127.0.0.1")

    @override_settings(
        SOCIAL_AUTH_PROVIDERS={
            "google": {"client_id": "gid", "client_secret": "gsecret"},
            "discord": {"client_id": "", "client_secret": ""},
            "github": {"client_id": "", "client_secret": ""},
            "facebook": {"client_id": "", "client_secret": ""},
            "microsoft": {"client_id": "", "client_secret": ""},
        }
    )
    def test_social_helper_config_and_urls(self):
        providers = auth_utils.list_enabled_social_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["provider"], "google")

        config = auth_utils.get_social_provider_config("google")
        authorize_url = auth_utils.build_social_authorize_url(
            config,
            state="state-token",
            redirect_uri="http://localhost:8000/auth/social/google/callback/",
        )
        self.assertIn("state=state-token", authorize_url)

        self.assertEqual(auth_utils.slugify_username("John Doe"), "john_doe")
        self.assertEqual(auth_utils.split_name("John Doe"), ("John", "Doe"))
        self.assertIsNotNone(auth_utils.parse_iso_datetime("2026-03-03T10:00:00Z"))

    def test_send_password_reset_email_sync_success_and_exception(self):
        with patch("authentication.utils.render_to_string", return_value="<html/>"), patch(
            "authentication.utils.SMTP"
        ) as mocked_smtp:
            smtp_instance = mocked_smtp.return_value.__enter__.return_value
            auth_utils._send_password_reset_email(self.user, "raw-token")
        self.assertTrue(smtp_instance.send_message.called)

        with patch("authentication.utils.render_to_string", return_value="<html/>"), patch(
            "authentication.utils.SMTP", side_effect=Exception("smtp-error")
        ), patch("builtins.print") as mocked_print:
            auth_utils._send_password_reset_email(self.user, "raw-token")
        self.assertTrue(mocked_print.called)

    def test_send_verification_email_sync_success_and_exception(self):
        with patch("authentication.utils.render_to_string", return_value="<html/>"), patch(
            "authentication.utils.SMTP"
        ) as mocked_smtp:
            smtp_instance = mocked_smtp.return_value.__enter__.return_value
            auth_utils._send_verification_email(self.user, "verify-token")
        self.assertTrue(smtp_instance.send_message.called)

        with patch("authentication.utils.render_to_string", return_value="<html/>"), patch(
            "authentication.utils.SMTP", side_effect=Exception("smtp-error")
        ), patch("builtins.print") as mocked_print:
            auth_utils._send_verification_email(self.user, "verify-token")
        self.assertTrue(mocked_print.called)

    def test_send_email_async_helpers_start_thread(self):
        thread_mock = MagicMock()
        with patch("authentication.utils.threading.Thread", return_value=thread_mock) as mocked_thread:
            auth_utils.send_password_reset_email_async(self.user, "token-1")
            mocked_thread.assert_called_with(
                target=auth_utils._send_password_reset_email,
                args=(self.user, "token-1"),
                daemon=True,
            )
        self.assertTrue(thread_mock.start.called)

        thread_mock = MagicMock()
        with patch("authentication.utils.threading.Thread", return_value=thread_mock) as mocked_thread:
            auth_utils.send_verification_email_async(self.user, "token-2")
            mocked_thread.assert_called_with(
                target=auth_utils._send_verification_email,
                args=(self.user, "token-2"),
                daemon=True,
            )
        self.assertTrue(thread_mock.start.called)
