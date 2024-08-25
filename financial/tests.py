from datetime import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from financial.models import Contract, Invoice, Payment


class FinancialTestCase(TestCase):
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

        contract_1 = Contract.objects.create(
            name="test 1", user=user
        )

        invoice_1 = Invoice.objects.create(
            type=Invoice.TYPE_DEBIT,
            name="test invoice 1",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            contract=contract_1,
            user=user,
        )

        invoice_2 = Invoice.objects.create(
            type=Invoice.TYPE_DEBIT,
            name="test invoice 2",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            contract=contract_1,
            user=user,
        )

        payment_1 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="test payment 1",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            invoice=invoice_1,
            user=user,
        )

        payment_2 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="test payment 2",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            invoice=invoice_2,
            user=user,
        )

        payment_3 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="test payment 3",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            invoice=invoice_2,
            user=user,
        )

        contract_2 = Contract.objects.create(
            name="test 2", user=user
        )

        invoice_3 = Invoice.objects.create(
            type=Invoice.TYPE_DEBIT,
            name="test invoice 3",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            contract=contract_2,
            user=user,
        )

        payment_4 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="test payment 4",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            invoice=invoice_3,
            user=user,
        )

        contract_3 = Contract.objects.create(
            name="test 3", user=user
        )

        payment_5 = Invoice.objects.create(
            type=Invoice.TYPE_DEBIT,
            name="test invoice 4",
            date=datetime.now().date(),
            payment_date=datetime.now().date(),
            contract=contract_3,
            user=user,
        )

        payment_1.set_value(100)

        payment_2.set_value(100)
        payment_2.close_value()

        payment_3.set_value(100)

        payment_4.set_value(100)

        payment_5.set_value(100)

    def setUp(self) -> None:
        self.client.defaults["HTTP_AUTHORIZATION"] = (
            "Bearer " + self.token_json["tokens"]["access"]
        )

    def test_contract_value_total(self):
        """Valor total = valor aberto + valor fechado"""
        test_1 = Contract.objects.get(name='test 1')
        test_2 = Contract.objects.get(name='test 2')

        self.assertEqual(test_1.value, (test_1.value_open + test_1.value_closed))
        self.assertEqual(test_2.value, (test_2.value_open + test_2.value_closed))

    def test_invoice_value_total(self):
        """Valor total = valor aberto + valor fechado"""
        test_1 = Invoice.objects.get(name='test invoice 1')
        test_2 = Invoice.objects.get(name='test invoice 2')
        test_3 = Invoice.objects.get(name='test invoice 3')

        self.assertEqual(test_1.value, (test_1.value_open + test_1.value_closed))
        self.assertEqual(test_2.value, (test_2.value_open + test_2.value_closed))
        self.assertEqual(test_3.value, (test_3.value_open + test_3.value_closed))

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

        response = client.get(
            "/financial/contract/new", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/contract/1/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/contract/1/invoices/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/contract/1/invoice/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/contract/1/merge/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/invoice/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/invoice/1/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/invoice/1/payments/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/invoice/1/tags", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/payment/month/", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/new-payment", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/tag/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/tag/new", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/update_all_contracts_value", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/1/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/1/save", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/1/payoff", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get("/financial/report/", data={"page": 1, "page_size": 5})
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/count_payment", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/amount_payment", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/amount_payment_open", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/amount_payment_closed", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/amount_invoice_by_tag", data={"page": 1, "page_size": 5}
        )
        self.assertEqual(response.status_code, 403)

        response = client.get(
            "/financial/report/amount_forecast_value", data={"page": 1, "page_size": 5}
        )
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
        """Testa filtros de contrato"""
        response = self.client.get(
            "/financial/contract/", data={"page": 1, "page_size": 5, "id": 3}
        )
        response_body = json.loads(response.content)
        contract_data = response_body["data"]["data"]

        self.assertEqual(contract_data.__len__(), 1)

    def test_include_contract(self):
        """Testa incluir novo contrato"""
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

    def test_invoice_list(self):
        """Testa se retorna todas notas"""
        response = self.client.get(
            "/financial/invoice/", data={"page": 1, "page_size": 5}
        )
        response_body = json.loads(response.content)
        invoice_data = response_body["data"]["data"]

        self.assertEqual(invoice_data.__len__(), 4)

    def test_payment_list(self):
        """Testa se retorna todos pagamentos"""
        response = self.client.get("/financial/", data={"page": 1, "page_size": 5})
        response_body = json.loads(response.content)
        payment_data = response_body["data"]["data"]

        self.assertEqual(payment_data.__len__(), 4)

    def test_contract_value(self):
        """Testa os valores de contrato"""
        response = self.client.get("/financial/contract/1/")
        response_body = json.loads(response.content)
        contract_data = response_body['data']

        value = contract_data.get('value')
        value_open = contract_data.get('value_open')
        value_closed = contract_data.get('value_closed')

        self.assertEqual(value, 300)
        self.assertEqual(value_open, 200)
        self.assertEqual(value_closed, 100)
