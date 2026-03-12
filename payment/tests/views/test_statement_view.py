import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class StatementViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        normal_user = User.objects.create_user(username="normal", email="normal@normal.com", password="123")

        cls.tag1 = Tag.objects.create(name="Moradia", color="#ff4d4f", user=user)
        cls.tag2 = Tag.objects.create(name="Alimentacao", color="#00ff00", user=user)

        cls.invoice1 = Invoice.objects.create(
            name="Fatura Janeiro",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 10),
            fixed=False,
            value=Decimal("2500.00"),
            value_open=Decimal("0.00"),
            user=user,
        )
        cls.invoice1.tags.add(cls.tag1)

        cls.invoice2 = Invoice.objects.create(
            name="Receita",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 5),
            fixed=False,
            value=Decimal("8000.00"),
            value_open=Decimal("0.00"),
            user=user,
        )

        # Prior period payment (before date_from) — credit
        cls.prior_credit = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Salario Dezembro",
            description="Salario anterior",
            date=date(2025, 12, 1),
            payment_date=date(2025, 12, 5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("5000.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice2,
        )

        # Prior period payment (before date_from) — debit
        cls.prior_debit = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Aluguel Dezembro",
            description="Aluguel anterior",
            date=date(2025, 12, 1),
            payment_date=date(2025, 12, 10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("2000.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice1,
        )

        # In-period credit (type=0, status=1)
        cls.period_credit = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Salario",
            description="Pagamento mensal",
            date=date(2026, 1, 1),
            payment_date=date(2026, 1, 5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("8000.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice2,
        )

        # In-period debit (type=1, status=1)
        cls.period_debit = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Aluguel",
            description="Apartamento centro",
            date=date(2026, 1, 10),
            payment_date=date(2026, 1, 10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("2500.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice1,
        )

        # Open payment (status=0) — should NOT appear in statement
        cls.open_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Conta Pendente",
            description="Nao pago",
            date=date(2026, 1, 15),
            payment_date=date(2026, 1, 15),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("500.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice1,
        )

        # Payment belonging to another user — should NOT appear
        other_invoice = Invoice.objects.create(
            name="Outro",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 5),
            fixed=False,
            value=Decimal("100.00"),
            value_open=Decimal("0.00"),
            user=normal_user,
        )
        cls.other_user_payment = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Outro usuario",
            description="",
            date=date(2026, 1, 1),
            payment_date=date(2026, 1, 5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("999.00"),
            status=Payment.STATUS_DONE,
            user=normal_user,
            invoice=other_invoice,
        )

        token = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )
        cls.cookies = token.cookies

        token_normal = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "normal", "password": "123"},
        )
        cls.cookies_normal = token_normal.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_statement_success(self):
        """Testa extrato completo com summary e transactions corretos"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]

        summary = data["summary"]
        # opening_balance = 5000 (prior credit) - 2000 (prior debit) = 3000
        self.assertEqual(summary["opening_balance"], 3000.00)
        self.assertEqual(summary["total_credits"], 8000.00)
        self.assertEqual(summary["total_debits"], 2500.00)
        # closing = 3000 + 8000 - 2500 = 8500
        self.assertEqual(summary["closing_balance"], 8500.00)

        transactions = data["transactions"]
        # Only paid payments in period (2 items)
        self.assertEqual(len(transactions), 2)

    def test_statement_transaction_order_and_running_balance(self):
        """Testa que transacoes estao ordenadas por payment_date ASC, id ASC e running_balance esta correto"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        data = json.loads(response.content)["data"]
        transactions = data["transactions"]

        # First: credit on 2026-01-05 (Salario 8000)
        self.assertEqual(transactions[0]["name"], "Salario")
        self.assertEqual(transactions[0]["type"], Payment.TYPE_CREDIT)
        self.assertEqual(transactions[0]["value"], 8000.00)
        # running: 3000 + 8000 = 11000
        self.assertEqual(transactions[0]["running_balance"], 11000.00)

        # Second: debit on 2026-01-10 (Aluguel 2500)
        self.assertEqual(transactions[1]["name"], "Aluguel")
        self.assertEqual(transactions[1]["type"], Payment.TYPE_DEBIT)
        self.assertEqual(transactions[1]["value"], 2500.00)
        # running: 11000 - 2500 = 8500
        self.assertEqual(transactions[1]["running_balance"], 8500.00)

    def test_statement_transaction_fields(self):
        """Testa que cada transacao tem todos os campos esperados"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        data = json.loads(response.content)["data"]
        tx = data["transactions"][0]

        expected_fields = [
            "id", "name", "description", "payment_date", "date",
            "type", "value", "running_balance", "invoice_name", "tags",
        ]
        for field in expected_fields:
            self.assertIn(field, tx)

    def test_statement_tags_included(self):
        """Testa que tags da invoice aparecem nas transacoes"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        data = json.loads(response.content)["data"]
        # The debit (Aluguel) is from invoice1 which has tag1 (Moradia)
        debit_tx = data["transactions"][1]
        self.assertEqual(debit_tx["invoice_name"], "Fatura Janeiro")
        self.assertEqual(len(debit_tx["tags"]), 1)
        self.assertEqual(debit_tx["tags"][0]["name"], "Moradia")
        self.assertEqual(debit_tx["tags"][0]["color"], "#ff4d4f")

    def test_statement_empty_period(self):
        """Testa periodo sem transacoes — closing_balance deve ser igual ao opening_balance"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-06-01", "date_to": "2026-06-30"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]

        self.assertEqual(len(data["transactions"]), 0)
        self.assertEqual(data["summary"]["closing_balance"], data["summary"]["opening_balance"])
        self.assertEqual(data["summary"]["total_credits"], 0.0)
        self.assertEqual(data["summary"]["total_debits"], 0.0)

    def test_statement_missing_date_from(self):
        """Testa erro quando date_from esta ausente"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_to": "2026-01-31"},
        )

        self.assertEqual(response.status_code, 400)

    def test_statement_missing_date_to(self):
        """Testa erro quando date_to esta ausente"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 400)

    def test_statement_missing_both_dates(self):
        """Testa erro quando ambos parametros estao ausentes"""
        response = self.client.get(reverse("financial_statement"))

        self.assertEqual(response.status_code, 400)

    def test_statement_invalid_date_format(self):
        """Testa erro quando formato da data eh invalido"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "01-01-2026", "date_to": "2026-01-31"},
        )

        self.assertEqual(response.status_code, 400)

    def test_statement_no_authentication(self):
        """Testa acesso sem autenticacao"""
        self.client.cookies.clear()

        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        self.assertIn(response.status_code, [401, 403])

    def test_statement_unauthorized_user(self):
        """Testa acesso com usuario sem permissao financial"""
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        self.assertIn(response.status_code, [401, 403])

    def test_statement_wrong_method_post(self):
        """Testa erro com metodo POST"""
        response = self.client.post(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        self.assertEqual(response.status_code, 405)

    def test_statement_excludes_open_payments(self):
        """Testa que pagamentos abertos (status=0) nao aparecem no extrato"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        data = json.loads(response.content)["data"]
        tx_ids = [tx["id"] for tx in data["transactions"]]
        self.assertNotIn(self.open_payment.id, tx_ids)

    def test_statement_excludes_other_user_payments(self):
        """Testa que pagamentos de outros usuarios nao aparecem"""
        response = self.client.get(
            reverse("financial_statement"),
            {"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        data = json.loads(response.content)["data"]
        tx_ids = [tx["id"] for tx in data["transactions"]]
        self.assertNotIn(self.other_user_payment.id, tx_ids)
