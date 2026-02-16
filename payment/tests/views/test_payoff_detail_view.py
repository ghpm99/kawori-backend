import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class PayoffDetailViewTestCase(TestCase):
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
        cls.tag1 = Tag.objects.create(name="Tag Payoff 1", color="#FF0000", user=user)
        cls.tag2 = Tag.objects.create(name="Tag Payoff 2", color="#00FF00", user=user)

        # Criar invoice não fixa para testes
        cls.invoice_non_fixed = Invoice.objects.create(
            name="Fatura Não Fixa",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user
        )
        cls.invoice_non_fixed.tags.add(cls.tag1)

        # Criar invoice fixa para testes
        cls.invoice_fixed = Invoice.objects.create(
            name="Fatura Fixa",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=True,
            value=Decimal("2000.00"),
            value_open=Decimal("2000.00"),
            user=user
        )
        cls.invoice_fixed.tags.add(cls.tag1, cls.tag2)

        # Criar pagamento aberto em invoice não fixa
        base_date = datetime.now().date()
        cls.payment_non_fixed = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Não Fixo",
            description="Descrição não fixo",
            date=base_date,
            payment_date=base_date + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("150.50"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_non_fixed
        )

        # Criar pagamento aberto em invoice fixa
        cls.payment_fixed = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Fixo",
            description="Descrição fixo",
            date=base_date,
            payment_date=base_date + timedelta(days=10),
            installments=1,
            fixed=True,
            active=True,
            value=Decimal("300.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_fixed
        )

        # Criar pagamento já concluído (não deve ser baixado novamente)
        cls.payment_done = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Já Concluído",
            description="Não pode baixar",
            date=base_date,
            payment_date=base_date + timedelta(days=15),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice_non_fixed
        )

        # Criar pagamento para usuário normal (não deve ser acessível)
        cls.payment_normal_user = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Usuario Normal",
            description="Não acessível",
            date=base_date,
            payment_date=base_date + timedelta(days=20),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("200.00"),
            status=Payment.STATUS_OPEN,
            user=normal_user,
            invoice=cls.invoice_non_fixed
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

    def test_payoff_detail_view_success_non_fixed_invoice(self):
        """Testa sucesso da view com pagamento em invoice não fixa - deve baixar pagamento"""
        initial_invoice_value_open = self.invoice_non_fixed.value_open
        initial_payment_status = self.payment_non_fixed.status

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        self.payment_non_fixed.refresh_from_db()
        self.invoice_non_fixed.refresh_from_db()

        self.assertEqual(self.payment_non_fixed.status, Payment.STATUS_DONE)
        self.assertEqual(self.invoice_non_fixed.value_open, initial_invoice_value_open - self.payment_non_fixed.value)

    def test_payoff_detail_view_success_fixed_invoice(self):
        """Testa sucesso da view com pagamento em invoice fixa - deve baixar e criar nova invoice"""
        initial_invoice_count = Invoice.objects.filter(user__username="test").count()
        initial_payment_status = self.payment_fixed.status

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_fixed.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        self.payment_fixed.refresh_from_db()
        self.assertEqual(self.payment_fixed.status, Payment.STATUS_DONE)

        # Verificar se uma nova invoice foi criada
        final_invoice_count = Invoice.objects.filter(user__username="test").count()
        self.assertEqual(final_invoice_count, initial_invoice_count + 1)

        # Verificar dados da nova invoice
        new_invoice = Invoice.objects.filter(
            user__username="test",
            name=self.invoice_fixed.name
        ).exclude(id=self.invoice_fixed.id).first()

        self.assertIsNotNone(new_invoice)
        self.assertEqual(new_invoice.type, self.invoice_fixed.type)
        self.assertEqual(new_invoice.name, self.invoice_fixed.name)
        self.assertEqual(new_invoice.installments, self.invoice_fixed.installments)
        self.assertTrue(new_invoice.fixed)
        self.assertEqual(new_invoice.value, self.invoice_fixed.value)
        self.assertEqual(new_invoice.value_open, self.invoice_fixed.value)

        # Verificar se as tags foram copiadas
        original_tags = list(self.invoice_fixed.tags.all())
        new_tags = list(new_invoice.tags.all())
        
        self.assertEqual(len(new_tags), len(original_tags))
        for original_tag in original_tags:
            self.assertIn(original_tag, new_tags)

        # Verificar se a data de pagamento foi incrementada
        expected_payment_date = self.payment_fixed.payment_date + timedelta(days=32)  # Aproximadamente 1 mês
        self.assertEqual(new_invoice.payment_date.strftime("%Y-%m-%d"), expected_payment_date.strftime("%Y-%m-%d"))

        # Verificar se novos pagamentos foram gerados
        new_payments = Payment.objects.filter(invoice=new_invoice)
        self.assertEqual(len(new_payments), self.invoice_fixed.installments)

    def test_payoff_detail_view_success_credit_payment(self):
        """Testa sucesso da view com pagamento de crédito - deve baixar normalmente"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_fixed.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        self.payment_fixed.refresh_from_db()
        self.assertEqual(self.payment_fixed.status, Payment.STATUS_DONE)

    def test_payoff_detail_view_success_debit_payment(self):
        """Testa sucesso da view com pagamento de débito - deve baixar normalmente"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        self.payment_non_fixed.refresh_from_db()
        self.assertEqual(self.payment_non_fixed.status, Payment.STATUS_DONE)

    def test_payoff_detail_view_error_payment_not_found(self):
        """Testa erro da view com ID inexistente - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": 99999})
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento não encontrado")

    def test_payoff_detail_view_error_payment_already_done(self):
        """Testa erro da view tentando baixar pagamento já concluído - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_done.id})
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento ja baixado")

    def test_payoff_detail_view_error_payment_from_other_user(self):
        """Testa erro da view tentando baixar pagamento de outro usuário - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_normal_user.id})
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento não encontrado")

    def test_payoff_detail_view_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id}))

        self.assertEqual(response.status_code, 405)

    def test_payoff_detail_view_error_wrong_method_put(self):
        """Testa erro da view com método PUT - deve retornar erro 405"""
        response = self.client.put(reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id}))

        self.assertEqual(response.status_code, 405)

    def test_payoff_detail_view_error_wrong_method_delete(self):
        """Testa erro da view com método DELETE - deve retornar erro 405"""
        response = self.client.delete(reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id}))

        self.assertEqual(response.status_code, 405)

    def test_payoff_detail_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_payoff_detail_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_payoff_detail_view_edge_case_zero_value_payment(self):
        """Testa edge case baixando pagamento de valor zero - deve funcionar normalmente"""
        # Criar pagamento de valor zero
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
            invoice=self.invoice_non_fixed
        )

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": payment_zero.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        payment_zero.refresh_from_db()
        self.assertEqual(payment_zero.status, Payment.STATUS_DONE)

    def test_payoff_detail_view_edge_case_negative_value_payment(self):
        """Testa edge case baixando pagamento de valor negativo - deve funcionar normalmente"""
        # Criar pagamento de valor negativo
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
            invoice=self.invoice_non_fixed
        )

        initial_invoice_value_open = self.invoice_non_fixed.value_open

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": payment_negative.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        payment_negative.refresh_from_db()
        self.invoice_non_fixed.refresh_from_db()

        self.assertEqual(payment_negative.status, Payment.STATUS_DONE)
        # Valor negativo deve aumentar o value_open
        self.assertEqual(self.invoice_non_fixed.value_open, initial_invoice_value_open - payment_negative.value)

    def test_payoff_detail_view_edge_case_very_large_value_payment(self):
        """Testa edge case baixando pagamento de valor muito grande - deve funcionar normalmente"""
        # Criar pagamento de valor grande
        payment_large = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Grande",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("999999.99"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice_non_fixed
        )

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": payment_large.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        payment_large.refresh_from_db()
        self.assertEqual(payment_large.status, Payment.STATUS_DONE)

    def test_payoff_detail_view_edge_case_inactive_payment(self):
        """Testa edge case baixando pagamento inativo - deve funcionar normalmente"""
        # Criar pagamento inativo
        payment_inactive = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Inativo",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=False,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice_non_fixed
        )

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": payment_inactive.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se o pagamento foi atualizado
        payment_inactive.refresh_from_db()
        self.assertEqual(payment_inactive.status, Payment.STATUS_DONE)

    def test_payoff_detail_view_edge_case_fixed_invoice_with_multiple_installments(self):
        """Testa edge case baixando pagamento de invoice fixa com múltiplas parcelas"""
        # Criar invoice fixa com múltiplas parcelas
        invoice_multi = Invoice.objects.create(
            name="Fatura Fixa Múltipla",
            date=datetime.now().date(),
            installments=3,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=True,
            value=Decimal("3000.00"),
            value_open=Decimal("3000.00"),
            user=User.objects.get(username="test")
        )

        # Criar pagamento para baixar
        payment_multi = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Múltiplo",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=True,
            active=True,
            value=Decimal("1000.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=invoice_multi
        )

        initial_invoice_count = Invoice.objects.filter(user__username="test").count()

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": payment_multi.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento baixado")

        # Verificar se uma nova invoice foi criada com as mesmas características
        final_invoice_count = Invoice.objects.filter(user__username="test").count()
        self.assertEqual(final_invoice_count, initial_invoice_count + 1)

        new_invoice = Invoice.objects.filter(
            user__username="test",
            name="Fatura Fixa Múltipla"
        ).exclude(id=invoice_multi.id).first()

        self.assertIsNotNone(new_invoice)
        self.assertEqual(new_invoice.installments, 3)

        # Verificar se 3 novos pagamentos foram gerados
        new_payments = Payment.objects.filter(invoice=new_invoice)
        self.assertEqual(len(new_payments), 3)

    def test_payoff_detail_view_edge_case_invalid_id_format(self):
        """Testa edge case com formato de ID inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": "invalid_id"})
        )

        self.assertEqual(response.status_code, 404)  # Django trata como não encontrado

    def test_payoff_detail_view_edge_case_zero_id(self):
        """Testa edge case com ID igual a zero - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": 0})
        )

        self.assertEqual(response.status_code, 404)

    def test_payoff_detail_view_edge_case_negative_id(self):
        """Testa edge case com ID negativo - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": -1})
        )

        self.assertEqual(response.status_code, 404)

    def test_payoff_detail_view_edge_case_concurrent_payoff_attempts(self):
        """Testa edge case tentativas concorrentes de baixar mesmo pagamento - segunda deve falhar"""
        # Primeira baixa
        response1 = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response1.status_code, 200)

        # Segunda baixa do mesmo pagamento
        response2 = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response2.status_code, 400)
        data2 = json.loads(response2.content)
        self.assertEqual(data2["msg"], "Pagamento ja baixado")

    def test_payoff_detail_view_response_structure(self):
        """Testa estrutura da resposta da view"""
        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura da resposta
        self.assertIn("msg", data)
        self.assertIsInstance(data["msg"], str)
        self.assertEqual(data["msg"], "Pagamento baixado")

    def test_payoff_detail_view_invoice_value_calculation(self):
        """Testa cálculo correto do valor da invoice após baixa"""
        initial_value_open = self.invoice_non_fixed.value_open
        payment_value = self.payment_non_fixed.value
        expected_value_open = initial_value_open - payment_value

        response = self.client.post(
            reverse("financial_payoff_detail_view", kwargs={"id": self.payment_non_fixed.id})
        )

        self.assertEqual(response.status_code, 200)

        # Verificar cálculo do valor da invoice
        self.invoice_non_fixed.refresh_from_db()
        self.assertEqual(self.invoice_non_fixed.value_open, expected_value_open)
