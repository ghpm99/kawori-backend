import json
from django.test import Client, TestCase


# Create your tests here.
class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_fail_signup_user(self):
        """Testa se falha o cadastro"""
        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data={"username": "test_user", "password": "user123"},
        )

        response_json = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response_json['msg'], 'Todos os campos são obrigatórios.')

    def test_success_signup_user(self):
        """Testa o sucesso no cadastro"""
        user_data = {
            "username": "test_user",
            "password": "user123",
            "email": "email@teste.com",
            "name": "test",
            "last_name": "user"
        }

        response = self.client.post(
            "/auth/signup",
            content_type="application/json",
            data=user_data,
        )

        response_json = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_json['msg'], 'Usuário criado com sucesso!')
