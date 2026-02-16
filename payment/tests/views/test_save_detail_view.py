import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment


class SaveDetailViewTestCase(TestCase):
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
            name="Fatura Teste Save",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user
        )

        # Criar pagamento de teste aberto
        base_date = datetime.now().date()
        cls.payment_open = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Aberto Original",
            description="Descrição original",
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

        # Criar pagamento já concluído (não deve ser editável)
        cls.payment_done = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Concluído",
            description="Não pode editar",
            date=base_date,
            payment_date=base_date + timedelta(days=10),
            installments=1,
            fixed=True,
            active=True,
            value=Decimal("200.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice
        )

        # Criar pagamento para usuário normal (não deve ser acessível)
        cls.payment_normal_user = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Usuario Normal",
            description="Não acessível",
            date=base_date,
            payment_date=base_date + timedelta(days=15),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
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

    def test_save_detail_view_success_update_name(self):
        """Testa sucesso da view atualizando apenas o nome - deve atualizar corretamente"""
        update_data = {
            "name": "Pagamento Atualizado"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.name, "Pagamento Atualizado")
        # Outros campos não devem ter mudado
        self.assertEqual(self.payment_open.type, Payment.TYPE_DEBIT)
        self.assertEqual(self.payment_open.value, Decimal("150.50"))

    def test_save_detail_view_success_update_type(self):
        """Testa sucesso da view atualizando o tipo - deve atualizar corretamente"""
        update_data = {
            "type": Payment.TYPE_CREDIT
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.type, Payment.TYPE_CREDIT)

    def test_save_detail_view_success_update_payment_date(self):
        """Testa sucesso da view atualizando data de pagamento - deve atualizar corretamente"""
        new_date = "2026-03-15"
        update_data = {
            "payment_date": new_date
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(str(self.payment_open.payment_date), new_date)

    def test_save_detail_view_success_update_fixed(self):
        """Testa sucesso da view atualizando campo fixed - deve atualizar corretamente"""
        update_data = {
            "fixed": True
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.assertTrue(self.payment_open.fixed)

    def test_save_detail_view_success_update_active(self):
        """Testa sucesso da view atualizando campo active - deve atualizar corretamente"""
        update_data = {
            "active": False
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.assertFalse(self.payment_open.active)

    def test_save_detail_view_success_update_value(self):
        """Testa sucesso da view atualizando valor - deve atualizar valor e invoice"""
        old_value = self.payment_open.value
        new_value = "200.00"
        expected_invoice_value = float(self.invoice.value_open - old_value) + float(new_value)

        update_data = {
            "value": new_value
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se o pagamento foi atualizado
        self.payment_open.refresh_from_db()
        self.invoice.refresh_from_db()
        
        self.assertEqual(self.payment_open.value, Decimal(new_value))
        self.assertEqual(float(self.invoice.value_open), expected_invoice_value)

    def test_save_detail_view_success_update_multiple_fields(self):
        """Testa sucesso da view atualizando múltiplos campos - deve atualizar todos"""
        update_data = {
            "name": "Pagamento Múltiplos Campos",
            "type": Payment.TYPE_CREDIT,
            "payment_date": "2026-04-20",
            "fixed": True,
            "active": False,
            "value": "300.00"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

        # Verificar se todos os campos foram atualizados
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.name, "Pagamento Múltiplos Campos")
        self.assertEqual(self.payment_open.type, Payment.TYPE_CREDIT)
        self.assertEqual(str(self.payment_open.payment_date), "2026-04-20")
        self.assertTrue(self.payment_open.fixed)
        self.assertFalse(self.payment_open.active)
        self.assertEqual(self.payment_open.value, Decimal("300.00"))

    def test_save_detail_view_error_payment_not_found(self):
        """Testa erro da view com ID inexistente - deve retornar erro 404"""
        update_data = {
            "name": "Nome Inexistente"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": 99999}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Payment not found")

    def test_save_detail_view_error_payment_already_done(self):
        """Testa erro da view tentando atualizar pagamento já concluído - deve retornar erro 500"""
        update_data = {
            "name": "Tentativa de Edição"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_done.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento ja foi baixado")

    def test_save_detail_view_error_payment_from_other_user(self):
        """Testa erro da view tentando atualizar pagamento de outro usuário - deve retornar erro 404"""
        update_data = {
            "name": "Tentativa de Acesso"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_normal_user.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Payment not found")

    def test_save_detail_view_error_empty_body(self):
        """Testa erro da view com corpo vazio - deve retornar erro 500"""
        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data="",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 500)

    def test_save_detail_view_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 500"""
        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data="json_invalido",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 500)

    def test_save_detail_view_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}))

        self.assertEqual(response.status_code, 405)

    def test_save_detail_view_error_wrong_method_put(self):
        """Testa erro da view com método PUT - deve retornar erro 405"""
        response = self.client.put(reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}))

        self.assertEqual(response.status_code, 405)

    def test_save_detail_view_error_wrong_method_delete(self):
        """Testa erro da view com método DELETE - deve retornar erro 405"""
        response = self.client.delete(reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}))

        self.assertEqual(response.status_code, 405)

    def test_save_detail_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        update_data = {
            "name": "Tentativa Não Autorizada"
        }

        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_save_detail_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        update_data = {
            "name": "Sem Autenticação"
        }

        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_save_detail_view_edge_case_update_with_same_values(self):
        """Testa edge case atualizando com os mesmos valores - deve funcionar normalmente"""
        update_data = {
            "name": self.payment_open.name,
            "type": self.payment_open.type,
            "value": str(self.payment_open.value)
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Pagamento atualizado com sucesso")

    def test_save_detail_view_edge_case_update_value_to_zero(self):
        """Testa edge case atualizando valor para zero - deve atualizar corretamente"""
        update_data = {
            "value": "0.00"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o valor foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.value, Decimal("0.00"))

    def test_save_detail_view_edge_case_update_value_to_negative(self):
        """Testa edge case atualizando valor para negativo - deve atualizar corretamente"""
        update_data = {
            "value": "-100.00"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o valor foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.value, Decimal("-100.00"))

    def test_save_detail_view_edge_case_update_with_very_long_name(self):
        """Testa edge case atualizando com nome muito longo - deve funcionar normalmente"""
        long_name = "A" * 500  # 500 caracteres
        update_data = {
            "name": long_name
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o nome foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.name, long_name)

    def test_save_detail_view_edge_case_update_with_special_characters(self):
        """Testa edge case atualizando com caracteres especiais - deve funcionar normalmente"""
        special_name = "Pagamento com ñ, ç, @#$%&*() e \"aspas\" e 'apóstrofos'"
        update_data = {
            "name": special_name
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o nome foi atualizado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.name, special_name)

    def test_save_detail_view_edge_case_update_with_invalid_date_format(self):
        """Testa edge case atualizando com formato de data inválido - deve retornar erro"""
        update_data = {
            "payment_date": "15/02/2026"  # Formato inválido
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        # Deve retornar erro por formato de data inválido
        self.assertEqual(response.status_code, 500)

    def test_save_detail_view_edge_case_update_with_future_date(self):
        """Testa edge case atualizando com data no futuro - deve funcionar normalmente"""
        future_date = "2030-12-31"
        update_data = {
            "payment_date": future_date
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se a data foi atualizada
        self.payment_open.refresh_from_db()
        self.assertEqual(str(self.payment_open.payment_date), future_date)

    def test_save_detail_view_edge_case_update_with_past_date(self):
        """Testa edge case atualizando com data no passado - deve funcionar normalmente"""
        past_date = "2020-01-01"
        update_data = {
            "payment_date": past_date
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se a data foi atualizada
        self.payment_open.refresh_from_db()
        self.assertEqual(str(self.payment_open.payment_date), past_date)

    def test_save_detail_view_edge_case_update_with_invalid_type(self):
        """Testa edge case atualizando com tipo inválido - deve ignorar campo inválido"""
        update_data = {
            "type": "tipo_invalido"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se o tipo não foi alterado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.type, Payment.TYPE_DEBIT)

    def test_save_detail_view_edge_case_update_with_string_boolean(self):
        """Testa edge case atualizando campos booleanos com strings - deve funcionar"""
        update_data = {
            "fixed": "true",
            "active": "false"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se os campos booleanos foram atualizados
        self.payment_open.refresh_from_db()
        self.assertTrue(self.payment_open.fixed)
        self.assertFalse(self.payment_open.active)

    def test_save_detail_view_edge_case_update_with_numeric_boolean(self):
        """Testa edge case atualizando campos booleanos com números - deve funcionar"""
        update_data = {
            "fixed": 1,
            "active": 0
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se os campos booleanos foram atualizados
        self.payment_open.refresh_from_db()
        self.assertTrue(self.payment_open.fixed)
        self.assertFalse(self.payment_open.active)

    def test_save_detail_view_edge_case_update_partial_fields(self):
        """Testa edge case atualizando apenas alguns campos - deve atualizar apenas os fornecidos"""
        original_name = self.payment_open.name
        original_type = self.payment_open.type
        
        update_data = {
            "name": "Nome Atualizado Parcial"
        }

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": self.payment_open.id}),
            data=json.dumps(update_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar se apenas o nome foi alterado
        self.payment_open.refresh_from_db()
        self.assertEqual(self.payment_open.name, "Nome Atualizado Parcial")
        self.assertEqual(self.payment_open.type, original_type)  # Não deve ter mudado
