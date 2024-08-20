import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from financial.models import Contract


class ContractTestCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.client = Client()

        user = User.objects.create_superuser(
            username="test", email="test@test.com", password="123"
        )

        token = cls.client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )

        cls.token_json = json.loads(token.content)

        Contract.objects.create(
            name="test 1", value=0, value_open=0, value_closed=0, user=user
        )

        Contract.objects.create(
            name="test 2", value=100, value_open=0, value_closed=100, user=user
        )

        Contract.objects.create(
            name="test 3", value=100, value_open=100, value_closed=0, user=user
        )

    def setUp(self) -> None:
        self.client.defaults["HTTP_AUTHORIZATION"] = (
            "Bearer " + self.token_json["tokens"]["access"]
        )

    def test_contract_not_super_user(self):
        """Testa se usuario normal tem acesso"""
        User.objects.create_user(
            username="normal", email="normal@normal.com", password="123"
        )

        client = Client()
        token = client.post(
            "/auth/token/",
            content_type="application/json",
            data={"username": "normal", "password": "123"},
        )

        token_json = json.loads(token.content)

        client.defaults["HTTP_AUTHORIZATION"] = (
            "Bearer " + token_json["tokens"]["access"]
        )

        response = client.get("/financial/contract/", data={"page": 1, "page_size": 5})

        self.assertEqual(response.status_code, 403)

    def test_contract_list(self):
        """Testa se retorna todos contratos"""
        response = self.client.get(
            "/financial/contract/", data={"page": 1, "page_size": 5}
        )
        response_body = json.loads(response.content)
        contract_data = response_body["data"]["data"]

        self.assertEqual(contract_data.__len__(), 3)

    def test_contract_filter(self):
        response = self.client.get(
            "/financial/contract/", data={"page": 1, "page_size": 5, "id": 3}
        )
        response_body = json.loads(response.content)
        contract_data = response_body["data"]["data"]

        self.assertEqual(contract_data.__len__(), 1)

    def test_include_contract(self):
        response_new = self.client.post(
            "/financial/contract/new",
            content_type="application/json",
            data={"name": "teste new contract"},
        )
        response_new_body = json.loads(response_new.content)
        response_new_data = response_new_body["msg"]
        self.assertEqual(response_new_data, "Contrato incluso com sucesso")
        response = self.client.get(
            "/financial/contract/", data={"page": 1, "page_size": 5}
        )
        response_body = json.loads(response.content)
        contract_data = response_body["data"]["data"]

        contains_contract = False

        for contract in contract_data:
            if contract.get("name").__contains__("teste new contract"):
                contains_contract = True

        self.assertEqual(contains_contract, True)
