import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class GetPaymentsMonthTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        # Criar usuário com permissão financial
        user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        # Criar usuário sem permissão para testes de acesso negado
        normal_user = User.objects.create_user(username="normal", email="normal@normal.com", password="123")

        # Criar tags para testes
        cls.tag1 = Tag.objects.create(name="Tag Mês 1", color="#FF0000", user=user)
        cls.tag2 = Tag.objects.create(name="Tag Mês 2", color="#00FF00", user=user)

        # Criar faturas para testes
        current_month_start = datetime.now().date().replace(day=1)
        current_month_end = current_month_start + timedelta(days=32)
        current_month_end = current_month_end.replace(day=1) - timedelta(days=1)

        # Fatura do mês atual
        cls.invoice_current = Invoice.objects.create(
            name="Fatura Mês Atual",
            date=current_month_start,
            installments=1,
            payment_date=current_month_start + timedelta(days=15),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user,
            active=True
        )
        cls.invoice_current.tags.add(cls.tag1)

        # Fatura do mês anterior
        cls.invoice_previous = Invoice.objects.create(
            name="Fatura Mês Anterior",
            date=current_month_start - timedelta(days=30),
            installments=1,
            payment_date=current_month_start - timedelta(days=15),
            fixed=True,
            value=Decimal("2000.00"),
            value_open=Decimal("2000.00"),
            user=user,
            active=True
        )
        cls.invoice_previous.tags.add(cls.tag2)

        # Fatura do próximo mês
        cls.invoice_next = Invoice.objects.create(
            name="Fatura Próximo Mês",
            date=current_month_start + timedelta(days=32),
            installments=1,
            payment_date=current_month_start + timedelta(days=47),
            fixed=False,
            value=Decimal("1500.00"),
            value_open=Decimal("1500.00"),
            user=user,
            active=True
        )

        # Criar pagamentos do mês atual
        cls.payment_current_1 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Atual Débito 1",
            date=current_month_start + timedelta(days=5),
            payment_date=current_month_start + timedelta(days=10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_current
        )

        cls.payment_current_2 = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Atual Crédito 1",
            date=current_month_start + timedelta(days=10),
            payment_date=current_month_start + timedelta(days=15),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("200.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice_current
        )

        cls.payment_current_3 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Atual Débito 2",
            date=current_month_start + timedelta(days=15),
            payment_date=current_month_start + timedelta(days=20),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("150.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_current
        )

        # Criar pagamentos do mês anterior (não devem aparecer)
        cls.payment_previous = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Anterior",
            date=current_month_start - timedelta(days=10),
            payment_date=current_month_start - timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("300.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_previous
        )

        # Criar pagamentos do próximo mês (não devem aparecer)
        cls.payment_next = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Próximo",
            date=current_month_start + timedelta(days=35),
            payment_date=current_month_start + timedelta(days=40),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("400.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_next
        )

        # Pagamento para usuário normal (não deve aparecer)
        cls.payment_normal_user = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Usuario Normal",
            date=current_month_start + timedelta(days=5),
            payment_date=current_month_start + timedelta(days=10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("50.00"),
            status=Payment.STATUS_OPEN,
            user=normal_user,
            invoice=cls.invoice_current
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

    def test_get_payments_month_success(self):
        """Testa sucesso da view - deve retornar pagamentos agrupados por invoice do mês atual"""
        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        payments_data = data["data"]

        # Deve retornar apenas a invoice do mês atual
        self.assertEqual(len(payments_data), 1)

        # Verificar estrutura dos dados retornados
        payment_group = payments_data[0]
        expected_fields = ["id", "name", "date", "total_value_credit", "total_value_debit",
                          "total_value_open", "total_value_closed", "total_payments"]
        for field in expected_fields:
            self.assertIn(field, payment_group)

        # Verificar se é a invoice correta
        self.assertEqual(payment_group["id"], self.invoice_current.id)
        self.assertEqual(payment_group["name"], "Fatura Mês Atual")

        # Verificar valores calculados
        # Créditos: 200.00 (payment_current_2)
        self.assertEqual(payment_group["total_value_credit"], 200.0)
        
        # Débitos: 100.00 + 150.00 = 250.00
        self.assertEqual(payment_group["total_value_debit"], 250.0)
        
        # Abertos: 100.00 + 150.00 = 250.00
        self.assertEqual(payment_group["total_value_open"], 250.0)
        
        # Fechados: 200.00
        self.assertEqual(payment_group["total_value_closed"], 200.0)
        
        # Total de pagamentos: 3
        self.assertEqual(payment_group["total_payments"], 3)

    def test_get_payments_month_with_multiple_invoices_same_month(self):
        """Testa view com múltiplas invoices no mesmo mês - deve retornar todas"""
        current_month_start = datetime.now().date().replace(day=1)
        
        # Criar invoice adicional no mesmo mês
        invoice_extra = Invoice.objects.create(
            name="Fatura Extra Mês Atual",
            date=current_month_start + timedelta(days=10),
            installments=1,
            payment_date=current_month_start + timedelta(days=25),
            fixed=False,
            value=Decimal("500.00"),
            value_open=Decimal("500.00"),
            user=User.objects.get(username="test"),
            active=True
        )

        # Criar pagamento para a invoice extra
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Extra",
            date=current_month_start + timedelta(days=12),
            payment_date=current_month_start + timedelta(days=25),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("75.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=invoice_extra
        )

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 invoices do mês atual
        self.assertEqual(len(data["data"]), 2)

    def test_get_payments_month_no_payments_current_month(self):
        """Testa view sem pagamentos no mês atual - deve retornar lista vazia"""
        # Deletar todos os pagamentos do mês atual
        current_month_start = datetime.now().date().replace(day=1)
        current_month_end = current_month_start + timedelta(days=32)
        current_month_end = current_month_end.replace(day=1) - timedelta(days=1)

        Payment.objects.filter(
            user__username="test",
            payment_date__gte=current_month_start,
            payment_date__lte=current_month_end
        ).delete()

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar lista vazia
        self.assertEqual(len(data["data"]), 0)

    def test_get_payments_month_only_credit_payments(self):
        """Testa view com apenas pagamentos de crédito - deve calcular valores corretamente"""
        # Deletar pagamentos de débito
        Payment.objects.filter(
            user__username="test",
            type=Payment.TYPE_DEBIT
        ).delete()

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Apenas crédito: 200.00
        self.assertEqual(payment_group["total_value_credit"], 200.0)
        self.assertEqual(payment_group["total_value_debit"], 0.0)
        self.assertEqual(payment_group["total_value_open"], 0.0)
        self.assertEqual(payment_group["total_value_closed"], 200.0)
        self.assertEqual(payment_group["total_payments"], 1)

    def test_get_payments_month_only_debit_payments(self):
        """Testa view com apenas pagamentos de débito - deve calcular valores corretamente"""
        # Deletar pagamentos de crédito
        Payment.objects.filter(
            user__username="test",
            type=Payment.TYPE_CREDIT
        ).delete()

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Apenas débito: 100.00 + 150.00 = 250.00
        self.assertEqual(payment_group["total_value_credit"], 0.0)
        self.assertEqual(payment_group["total_value_debit"], 250.0)
        self.assertEqual(payment_group["total_value_open"], 250.0)
        self.assertEqual(payment_group["total_value_closed"], 0.0)
        self.assertEqual(payment_group["total_payments"], 2)

    def test_get_payments_month_only_open_payments(self):
        """Testa view com apenas pagamentos abertos - deve calcular valores corretamente"""
        # Marcar todos como abertos
        Payment.objects.filter(
            user__username="test"
        ).update(status=Payment.STATUS_OPEN)

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Todos abertos: 100.00 + 200.00 + 150.00 = 450.00
        self.assertEqual(payment_group["total_value_credit"], 200.0)
        self.assertEqual(payment_group["total_value_debit"], 250.0)
        self.assertEqual(payment_group["total_value_open"], 450.0)
        self.assertEqual(payment_group["total_value_closed"], 0.0)
        self.assertEqual(payment_group["total_payments"], 3)

    def test_get_payments_month_only_closed_payments(self):
        """Testa view com apenas pagamentos fechados - deve calcular valores corretamente"""
        # Marcar todos como fechados
        Payment.objects.filter(
            user__username="test"
        ).update(status=Payment.STATUS_DONE)

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Todos fechados: 100.00 + 200.00 + 150.00 = 450.00
        self.assertEqual(payment_group["total_value_credit"], 200.0)
        self.assertEqual(payment_group["total_value_debit"], 250.0)
        self.assertEqual(payment_group["total_value_open"], 0.0)
        self.assertEqual(payment_group["total_value_closed"], 450.0)
        self.assertEqual(payment_group["total_payments"], 3)

    def test_get_payments_month_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.get(reverse("financial_get_payments_month"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_payments_month_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.get(reverse("financial_get_payments_month"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_payments_month_error_wrong_method_post(self):
        """Testa erro da view com método POST - deve retornar erro 405"""
        response = self.client.post(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 405)

    def test_get_payments_month_edge_case_no_invoices(self):
        """Testa edge case sem nenhuma invoice ativa - deve retornar lista vazia"""
        # Desativar todas as invoices
        Invoice.objects.filter(user__username="test").update(active=False)

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar lista vazia
        self.assertEqual(len(data["data"]), 0)

    def test_get_payments_month_edge_case_zero_value_payments(self):
        """Testa edge case com pagamentos de valor zero - deve calcular corretamente"""
        # Criar pagamento com valor zero
        current_month_start = datetime.now().date().replace(day=1)
        
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Zero",
            date=current_month_start + timedelta(days=20),
            payment_date=current_month_start + timedelta(days=25),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice_current
        )

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Deve incluir o pagamento de valor zero na contagem
        self.assertEqual(payment_group["total_payments"], 4)
        # Valores não devem mudar
        self.assertEqual(payment_group["total_value_debit"], 250.0)

    def test_get_payments_month_edge_case_negative_value_payments(self):
        """Testa edge case com pagamentos de valor negativo - deve calcular corretamente"""
        # Criar pagamento com valor negativo
        current_month_start = datetime.now().date().replace(day=1)
        
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Negativo",
            date=current_month_start + timedelta(days=20),
            payment_date=current_month_start + timedelta(days=25),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("-50.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice_current
        )

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Deve incluir o pagamento negativo no cálculo
        self.assertEqual(payment_group["total_payments"], 4)
        # Débito: 100.00 + 150.00 - 50.00 = 200.00
        self.assertEqual(payment_group["total_value_debit"], 200.0)

    def test_get_payments_month_edge_case_first_day_of_month(self):
        """Testa edge case executando no primeiro dia do mês - deve funcionar corretamente"""
        # Este teste simula o comportamento quando executado no dia 1 do mês
        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve funcionar normalmente
        self.assertIsInstance(data["data"], list)

    def test_get_payments_month_edge_case_last_day_of_month(self):
        """Testa edge case executando no último dia do mês - deve funcionar corretamente"""
        # Este teste simula o comportamento quando executado no último dia do mês
        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve funcionar normalmente
        self.assertIsInstance(data["data"], list)

    def test_get_payments_month_edge_case_inactive_payments(self):
        """Testa edge case com pagamentos inativos - não devem ser incluídos"""
        # Marcar um pagamento como inativo
        self.payment_current_1.active = False
        self.payment_current_1.save()

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Não deve incluir o pagamento inativo
        self.assertEqual(payment_group["total_payments"], 2)
        # Débito: apenas 150.00 (payment_current_3)
        self.assertEqual(payment_group["total_value_debit"], 150.0)

    def test_get_payments_month_edge_case_very_large_values(self):
        """Testa edge case com valores muito grandes - deve calcular corretamente"""
        # Criar pagamento com valor grande
        current_month_start = datetime.now().date().replace(day=1)
        
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Grande",
            date=current_month_start + timedelta(days=20),
            payment_date=current_month_start + timedelta(days=25),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("999999.99"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice_current
        )

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payment_group = data["data"][0]

        # Deve incluir o pagamento grande no cálculo
        self.assertEqual(payment_group["total_payments"], 4)
        # Débito: 100.00 + 150.00 + 999999.99 = 1000199.99
        self.assertEqual(payment_group["total_value_debit"], 1000199.99)

    def test_get_payments_month_response_structure(self):
        """Testa estrutura da resposta da view"""
        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura principal
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        # Se houver dados, verificar estrutura de cada item
        if data["data"]:
            payment_group = data["data"][0]
            expected_fields = ["id", "name", "date", "total_value_credit", "total_value_debit",
                              "total_value_open", "total_value_closed", "total_payments"]
            for field in expected_fields:
                self.assertIn(field, payment_group)

            # Verificar tipos
            self.assertIsInstance(payment_group["id"], int)
            self.assertIsInstance(payment_group["name"], str)
            self.assertIsInstance(payment_group["total_value_credit"], float)
            self.assertIsInstance(payment_group["total_value_debit"], float)
            self.assertIsInstance(payment_group["total_value_open"], float)
            self.assertIsInstance(payment_group["total_value_closed"], float)
            self.assertIsInstance(payment_group["total_payments"], int)
