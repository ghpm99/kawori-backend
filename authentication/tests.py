import json

from django.contrib.auth.models import User
from django.test import Client, TestCase


# Create your tests here.
class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(
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
        response_json = json.loads(response.content)

        access_token = response_json["tokens"]["access"]
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

        response_json = json.loads(response.content)

        access_token = response_json["tokens"]["access"]

        self.assertIsNotNone(access_token)

        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer " + access_token

        response_user = self.client.get("/auth/user")

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
