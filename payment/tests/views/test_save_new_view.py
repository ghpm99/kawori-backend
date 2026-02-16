import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from payment.models import Payment


class SaveNewViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        # Criar usuário com permissão financial
        user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        # Criar usuário sem permissão para testes de acesso negado
        normal_user = User.objects.create_user(username="normal", email="normal@normal.com", password="123")

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

    def test_save_new_view_success_single_installment(self):
        """Testa sucesso da view com pagamento de parcela única - deve criar um pagamento"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Teste Único",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        initial_count = Payment.objects.filter(user__username="test").count()

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento incluso com sucesso")

        # Verificar se o pagamento foi criado
        final_count = Payment.objects.filter(user__username="test").count()
        self.assertEqual(final_count, initial_count + 1)

        # Verificar dados do pagamento criado
        payment = Payment.objects.filter(user__username="test", name="Pagamento Teste Único").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.type, Payment.TYPE_DEBIT)
        self.assertEqual(payment.name, "Pagamento Teste Único")
        self.assertEqual(payment.installments, 1)
        self.assertEqual(payment.value, Decimal("150.00"))
        self.assertFalse(payment.fixed)

    def test_save_new_view_success_multiple_installments(self):
        """Testa sucesso da view com pagamento parcelado - deve criar múltiplos pagamentos"""
        payment_data = {
            "type": Payment.TYPE_CREDIT,
            "name": "Pagamento Parcelado",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 3,
            "fixed": True,
            "value": "300.00"
        }

        initial_count = Payment.objects.filter(user__username="test").count()

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento incluso com sucesso")

        # Verificar se os pagamentos foram criados
        final_count = Payment.objects.filter(user__username="test").count()
        self.assertEqual(final_count, initial_count + 3)

        # Verificar dados dos pagamentos criados
        payments = Payment.objects.filter(user__username="test", name="Pagamento Parcelado").order_by("installments")
        self.assertEqual(len(payments), 3)

        # Verificar valores das parcelas (300/3 = 100 cada)
        expected_values = [Decimal("100.00"), Decimal("100.00"), Decimal("100.00")]
        for i, payment in enumerate(payments):
            self.assertEqual(payment.installments, i + 1)
            self.assertEqual(payment.value, expected_values[i])

        # Verificar datas de pagamento (incrementa mês a mês)
        expected_dates = [
            datetime(2026, 2, 20).date(),
            datetime(2026, 3, 20).date(),
            datetime(2026, 4, 20).date()
        ]
        for i, payment in enumerate(payments):
            self.assertEqual(payment.payment_date, expected_dates[i])

    def test_save_new_view_success_decimal_value_multiple_installments(self):
        """Testa sucesso com valor decimal que não divide exatamente - deve distribuir corretamente"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Decimal",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 3,
            "fixed": False,
            "value": "100.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se os pagamentos foram criados com valores corretos
        payments = Payment.objects.filter(user__username="test", name="Pagamento Decimal").order_by("installments")
        self.assertEqual(len(payments), 3)

        # A soma deve ser 100.00
        total_value = sum(payment.value for payment in payments)
        self.assertEqual(total_value, Decimal("100.00"))

    def test_save_new_view_error_missing_required_fields(self):
        """Testa erro da view sem campos obrigatórios - deve retornar erro"""
        # Testar sem nome
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 500 (campo obrigatório faltando)
        self.assertEqual(response.status_code, 500)

    def test_save_new_view_error_missing_type(self):
        """Testa erro da view sem tipo - deve retornar erro"""
        payment_data = {
            "name": "Pagamento Sem Tipo",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 500
        self.assertEqual(response.status_code, 500)

    def test_save_new_view_error_missing_value(self):
        """Testa erro da view sem valor - deve retornar erro"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Sem Valor",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 500
        self.assertEqual(response.status_code, 500)

    def test_save_new_view_error_missing_installments(self):
        """Testa erro da view sem número de parcelas - deve retornar erro"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Sem Parcelas",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 500
        self.assertEqual(response.status_code, 500)

    def test_save_new_view_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_save_new"),
            data="json_invalido",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_save_new_view_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_save_new"))

        self.assertEqual(response.status_code, 405)

    def test_save_new_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Não Autorizado",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_save_new_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Sem Auth",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_save_new_view_edge_case_zero_installments(self):
        """Testa edge case com zero parcelas - deve retornar erro"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Zero Parcelas",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 0,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Não deve criar nenhum pagamento
        self.assertEqual(response.status_code, 200)
        
        # Verificar que nenhum pagamento foi criado
        payment = Payment.objects.filter(user__username="test", name="Pagamento Zero Parcelas").first()
        self.assertIsNone(payment)

    def test_save_new_view_edge_case_negative_installments(self):
        """Testa edge case com parcelas negativas - deve retornar erro"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Parcelas Negativas",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": -1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Não deve criar nenhum pagamento
        self.assertEqual(response.status_code, 200)

    def test_save_new_view_edge_case_zero_value(self):
        """Testa edge case com valor zero - deve criar pagamentos com valor zero"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Zero Valor",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 2,
            "fixed": False,
            "value": "0.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se os pagamentos foram criados com valor zero
        payments = Payment.objects.filter(user__username="test", name="Pagamento Zero Valor")
        self.assertEqual(len(payments), 2)

        for payment in payments:
            self.assertEqual(payment.value, Decimal("0.00"))

    def test_save_new_view_edge_case_negative_value(self):
        """Testa edge case com valor negativo - deve criar pagamentos com valor negativo"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Valor Negativo",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "-150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o pagamento foi criado com valor negativo
        payment = Payment.objects.filter(user__username="test", name="Pagamento Valor Negativo").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.value, Decimal("-150.00"))

    def test_save_new_view_edge_case_very_large_installments(self):
        """Testa edge case com muitas parcelas - deve criar todos os pagamentos"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Muitas Parcelas",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 12,
            "fixed": False,
            "value": "1200.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se todos os 12 pagamentos foram criados
        payments = Payment.objects.filter(user__username="test", name="Pagamento Muitas Parcelas")
        self.assertEqual(len(payments), 12)

        # Verificar se a soma dos valores está correta
        total_value = sum(payment.value for payment in payments)
        self.assertEqual(total_value, Decimal("1200.00"))

    def test_save_new_view_edge_case_invalid_date_format(self):
        """Testa edge case com formato de data inválido - deve retornar erro"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Data Inválida",
            "date": "15/02/2026",  # Formato inválido
            "payment_date": "20/02/2026",  # Formato inválido
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        # Deve retornar erro por formato de data inválido
        self.assertEqual(response.status_code, 500)

    def test_save_new_view_edge_case_very_long_name(self):
        """Testa edge case com nome muito longo - deve criar pagamento normalmente"""
        long_name = "A" * 500  # 500 caracteres
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": long_name,
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o pagamento foi criado com o nome longo
        payment = Payment.objects.filter(user__username="test", name=long_name).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.name, long_name)

    def test_save_new_view_edge_case_special_characters_in_name(self):
        """Testa edge case com caracteres especiais no nome - deve criar pagamento normalmente"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento com ñ, ç, @#$%&*()",
            "date": "2026-02-15",
            "payment_date": "2026-02-20",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o pagamento foi criado com caracteres especiais
        payment = Payment.objects.filter(user__username="test", name="Pagamento com ñ, ç, @#$%&*()").first()
        self.assertIsNotNone(payment)

    def test_save_new_view_edge_case_future_dates(self):
        """Testa edge case com datas muito no futuro - deve criar pagamento normalmente"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Futuro",
            "date": "2030-12-31",
            "payment_date": "2031-01-15",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o pagamento foi criado com datas futuras
        payment = Payment.objects.filter(user__username="test", name="Pagamento Futuro").first()
        self.assertIsNotNone(payment)
        self.assertEqual(str(payment.date), "2030-12-31")
        self.assertEqual(str(payment.payment_date), "2031-01-15")

    def test_save_new_view_edge_case_past_dates(self):
        """Testa edge case com datas no passado - deve criar pagamento normalmente"""
        payment_data = {
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento Passado",
            "date": "2020-01-01",
            "payment_date": "2020-01-15",
            "installments": 1,
            "fixed": False,
            "value": "150.00"
        }

        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(payment_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o pagamento foi criado com datas passadas
        payment = Payment.objects.filter(user__username="test", name="Pagamento Passado").first()
        self.assertIsNotNone(payment)
        self.assertEqual(str(payment.date), "2020-01-01")
        self.assertEqual(str(payment.payment_date), "2020-01-15")
