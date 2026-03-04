import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment


class DetailViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        # Criar usuário com permissão financial
        user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        # Criar usuário sem permissão para testes de acesso negado
        normal_user = User.objects.create_user(username="normal", email="normal@normal.com", password="123")

        # Criar invoice para testes
        cls.invoice = Invoice.objects.create(
            name="Fatura Teste Detalhe",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user
        )

        # Criar pagamento de teste para o usuário com permissão
        base_date = datetime.now().date()
        cls.payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Teste Detalhe",
            description="Descrição do pagamento teste",
            date=base_date,
            payment_date=base_date + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("150.50"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice
        )

        # Criar pagamento para usuário normal (não deve ser acessível)
        cls.payment_normal_user = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Usuario Normal",
            description="Descrição do pagamento normal",
            date=base_date,
            payment_date=base_date + timedelta(days=10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("200.00"),
            status=Payment.STATUS_DONE,
            user=normal_user,
            invoice=cls.invoice
        )

        # Obter token de autenticação
        token = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )
        cls.cookies = token.cookies

        # Token para usuário normal
        token_normal = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "normal", "password": "123"},
        )
        cls.cookies_normal = token_normal.cookies

    def setUp(self):
        # Restaurar cookies para cada teste
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_detail_view_success(self):
        """Testa sucesso da view com ID válido - deve retornar detalhes do pagamento"""
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        payment_data = data["data"]

        # Verificar estrutura dos dados retornados
        expected_fields = ["id", "status", "type", "name", "date", "installments",
                          "payment_date", "fixed", "active", "value", "invoice", "invoice_name"]
        for field in expected_fields:
            self.assertIn(field, payment_data)

        # Verificar valores dos campos
        self.assertEqual(payment_data["id"], self.payment.id)
        self.assertEqual(payment_data["status"], self.payment.status)
        self.assertEqual(payment_data["type"], self.payment.type)
        self.assertEqual(payment_data["name"], self.payment.name)
        self.assertEqual(payment_data["installments"], self.payment.installments)
        self.assertEqual(payment_data["payment_date"], self.payment.payment_date.strftime("%Y-%m-%d"))
        self.assertEqual(payment_data["fixed"], self.payment.fixed)
        self.assertEqual(payment_data["active"], self.payment.active)
        self.assertEqual(payment_data["value"], float(self.payment.value))
        self.assertEqual(payment_data["invoice"], self.payment.invoice.id)
        self.assertEqual(payment_data["invoice_name"], self.payment.invoice.name)

    def test_detail_view_success_credit_payment(self):
        """Testa sucesso da view com pagamento de crédito - deve retornar dados corretos"""
        # Criar pagamento de crédito
        credit_payment = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Crédito Detalhe",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=2,
            fixed=True,
            active=True,
            value=Decimal("300.00"),
            status=Payment.STATUS_DONE,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": credit_payment.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["type"], Payment.TYPE_CREDIT)
        self.assertEqual(payment_data["status"], Payment.STATUS_DONE)
        self.assertEqual(payment_data["installments"], 2)
        self.assertTrue(payment_data["fixed"])

    def test_detail_view_success_fixed_payment(self):
        """Testa sucesso da view com pagamento fixo - deve retornar dados corretos"""
        # Criar pagamento fixo
        fixed_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Fixo Detalhe",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=True,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": fixed_payment.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertTrue(payment_data["fixed"])

    def test_detail_view_success_inactive_payment(self):
        """Testa sucesso da view com pagamento inativo - deve retornar dados corretos"""
        # Criar pagamento inativo
        inactive_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Inativo Detalhe",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=False,
            value=Decimal("50.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": inactive_payment.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertFalse(payment_data["active"])

    def test_detail_view_error_payment_not_found(self):
        """Testa erro da view com ID inexistente - deve retornar erro 404"""
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": 99999}))

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Payment not found")

    def test_detail_view_error_invalid_id_format(self):
        """Testa erro da view com formato de ID inválido - deve retornar erro 404"""
        response = self.client.get("/financial/payment/invalid_id/")

        self.assertEqual(response.status_code, 404)

    def test_detail_view_error_payment_from_other_user(self):
        """Testa erro da view tentando acessar pagamento de outro usuário - deve retornar erro 404"""
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": self.payment_normal_user.id}))

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Payment not found")

    def test_detail_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_detail_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_detail_view_error_wrong_method_post(self):
        """Testa erro da view com método POST - deve retornar erro 405"""
        response = self.client.post(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        self.assertEqual(response.status_code, 405)

    def test_detail_view_error_wrong_method_put(self):
        """Testa erro da view com método PUT - deve retornar erro 405"""
        response = self.client.put(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        self.assertEqual(response.status_code, 405)

    def test_detail_view_error_wrong_method_delete(self):
        """Testa erro da view com método DELETE - deve retornar erro 405"""
        response = self.client.delete(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        self.assertEqual(response.status_code, 405)

    def test_detail_view_edge_case_zero_id(self):
        """Testa edge case com ID igual a zero - deve retornar erro 404"""
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": 0}))

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Payment not found")

    def test_detail_view_edge_case_negative_id(self):
        """Testa edge case com ID negativo - deve retornar erro 404"""
        response = self.client.get("/financial/payment/-1/")

        self.assertEqual(response.status_code, 404)

    def test_detail_view_edge_case_payment_with_null_values(self):
        """Testa edge case com pagamento com valores nulos - deve retornar dados corretamente"""
        # Criar pagamento com valores nulos
        payment_null = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Nulo",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("0.00"),  # Valor zero em vez de nulo
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_null.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["value"], 0.0)

    def test_detail_view_edge_case_payment_with_very_long_name(self):
        """Testa edge case com pagamento com nome muito longo - deve retornar dados corretamente"""
        long_name = "A" * 500  # 500 caracteres
        
        payment_long = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name=long_name,
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_long.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["name"], long_name)

    def test_detail_view_edge_case_payment_with_special_characters(self):
        """Testa edge case com pagamento com caracteres especiais - deve retornar dados corretamente"""
        special_name = "Pagamento com ñ, ç, @#$%&*() e \"aspas\" e 'apóstrofos'"
        
        payment_special = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name=special_name,
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_special.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["name"], special_name)

    def test_detail_view_edge_case_payment_with_future_dates(self):
        """Testa edge case com pagamento com datas no futuro - deve retornar dados corretamente"""
        future_date = datetime.now().date() + timedelta(days=365)
        
        payment_future = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Futuro",
            date=future_date,
            payment_date=future_date + timedelta(days=30),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_future.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(str(payment_data["date"]), str(future_date))
        self.assertEqual(str(payment_data["payment_date"]), str(future_date + timedelta(days=30)))

    def test_detail_view_edge_case_payment_with_past_dates(self):
        """Testa edge case com pagamento com datas no passado - deve retornar dados corretamente"""
        past_date = datetime.now().date() - timedelta(days=365)
        
        payment_past = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Passado",
            date=past_date,
            payment_date=past_date + timedelta(days=30),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_DONE,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_past.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(str(payment_data["date"]), str(past_date))
        self.assertEqual(str(payment_data["payment_date"]), str(past_date + timedelta(days=30)))

    def test_detail_view_edge_case_payment_with_many_installments(self):
        """Testa edge case com pagamento com muitas parcelas - deve retornar dados corretamente"""
        payment_many = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Muitas Parcelas",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=24,
            fixed=False,
            active=True,
            value=Decimal("2400.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_many.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["installments"], 24)

    def test_detail_view_edge_case_payment_with_zero_value(self):
        """Testa edge case com pagamento de valor zero - deve retornar dados corretamente"""
        payment_zero = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Zero",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_zero.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["value"], 0.0)

    def test_detail_view_edge_case_payment_with_negative_value(self):
        """Testa edge case com pagamento de valor negativo - deve retornar dados corretamente"""
        payment_negative = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Negativo",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("-100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment_negative.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_data = data["data"]
        self.assertEqual(payment_data["value"], -100.0)

    def test_detail_view_response_structure(self):
        """Testa estrutura da resposta da view"""
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": self.payment.id}))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura principal
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], dict)

        # Verificar estrutura dos dados do pagamento
        payment_data = data["data"]
        expected_fields = ["id", "status", "type", "name", "date", "installments",
                          "payment_date", "fixed", "active", "value", "invoice", "invoice_name"]
        for field in expected_fields:
            self.assertIn(field, payment_data)

        # Verificar tipos
        self.assertIsInstance(payment_data["id"], int)
        self.assertIsInstance(payment_data["status"], int)
        self.assertIsInstance(payment_data["type"], int)
        self.assertIsInstance(payment_data["name"], str)
        self.assertIsInstance(payment_data["installments"], int)
        self.assertIsInstance(payment_data["fixed"], bool)
        self.assertIsInstance(payment_data["active"], bool)
        self.assertIsInstance(payment_data["value"], float)
        self.assertIsInstance(payment_data["invoice"], int)
        self.assertIsInstance(payment_data["invoice_name"], str)
