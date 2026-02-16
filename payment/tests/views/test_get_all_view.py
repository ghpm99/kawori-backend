import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class GetAllViewTestCase(TestCase):
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
        cls.tag1 = Tag.objects.create(name="Tag Teste 1", color="#FF0000", user=user)
        cls.tag2 = Tag.objects.create(name="Tag Teste 2", color="#00FF00", user=user)
        cls.budget_tag = Tag.objects.create(name="Budget Tag", color="#0000FF", user=user)

        # Criar faturas para testes
        cls.invoice1 = Invoice.objects.create(
            name="Fatura Teste 1",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user
        )
        cls.invoice1.tags.add(cls.tag1, cls.budget_tag)

        cls.invoice2 = Invoice.objects.create(
            name="Fatura Teste 2",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=True,
            value=Decimal("2000.00"),
            value_open=Decimal("2000.00"),
            user=user
        )
        cls.invoice2.tags.add(cls.tag2)

        # Criar pagamentos de teste para o usuário com permissão
        base_date = datetime.now().date()

        cls.payment_1 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Teste 1",
            date=base_date,
            payment_date=base_date + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.50"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice1
        )

        cls.payment_2 = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Teste 2",
            date=base_date - timedelta(days=10),
            payment_date=base_date - timedelta(days=5),
            installments=3,
            fixed=True,
            active=True,
            value=Decimal("200.75"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice2
        )

        cls.payment_3 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Parcelado Teste",
            date=base_date - timedelta(days=5),
            payment_date=base_date + timedelta(days=15),
            installments=12,
            fixed=False,
            active=True,
            value=Decimal("150.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice1
        )

        cls.payment_4 = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Inativo",
            date=base_date - timedelta(days=20),
            payment_date=base_date + timedelta(days=30),
            installments=1,
            fixed=True,
            active=False,
            value=Decimal("75.25"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice2
        )

        # Payment para usuário normal (não deve aparecer nos resultados do usuário test)
        cls.payment_normal_user = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Usuario Normal",
            date=base_date,
            payment_date=base_date + timedelta(days=10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("50.00"),
            status=Payment.STATUS_OPEN,
            user=normal_user,
            invoice=cls.invoice1
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

    def test_get_all_view_success_without_filters(self):
        """Testa sucesso da view sem filtros - deve retornar todos os pagamentos do usuário com dados da invoice"""
        response = self.client.get(reverse("financial_get_all"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertIn("current_page", data["data"])
        self.assertIn("total_pages", data["data"])
        self.assertIn("data", data["data"])
        self.assertIn("page_size", data["data"])

        # Deve retornar 4 pagamentos (todos do usuário test)
        self.assertEqual(len(data["data"]["data"]), 4)

        # Verificar estrutura dos dados retornados
        payment_data = data["data"]["data"][0]
        expected_fields = ["id", "status", "type", "name", "date", "installments",
                          "payment_date", "fixed", "value", "invoice_id", "invoice_name", "tags"]
        for field in expected_fields:
            self.assertIn(field, payment_data)

        # Verificar se os dados da invoice estão presentes
        self.assertIsInstance(payment_data["invoice_id"], int)
        self.assertIsInstance(payment_data["invoice_name"], str)
        self.assertIsInstance(payment_data["tags"], list)

    def test_get_all_view_with_status_filter_open(self):
        """Testa filtro por status 'open' - deve retornar apenas pagamentos abertos"""
        response = self.client.get(reverse("financial_get_all"), {"status": "open"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos abertos
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_OPEN)

    def test_get_all_view_with_status_filter_done(self):
        """Testa filtro por status 'done' - deve retornar apenas pagamentos concluídos"""
        response = self.client.get(reverse("financial_get_all"), {"status": "done"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento concluído
        self.assertEqual(len(data["data"]["data"]), 1)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_DONE)

    def test_get_all_view_with_type_filter_debit(self):
        """Testa filtro por tipo 'debit' - deve retornar apenas débitos"""
        response = self.client.get(reverse("financial_get_all"), {"type": Payment.TYPE_DEBIT})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 débitos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["type"], Payment.TYPE_DEBIT)

    def test_get_all_view_with_type_filter_credit(self):
        """Testa filtro por tipo 'credit' - deve retornar apenas créditos"""
        response = self.client.get(reverse("financial_get_all"), {"type": Payment.TYPE_CREDIT})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 créditos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["type"], Payment.TYPE_CREDIT)

    def test_get_all_view_with_name_filter(self):
        """Testa filtro por nome (case insensitive) - deve retornar pagamentos com o termo"""
        response = self.client.get(reverse("financial_get_all"), {"name__icontains": "teste"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos com "teste" no nome
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertIn("teste", payment["name"].lower())

    def test_get_all_view_with_invoice_id_filter(self):
        """Testa filtro por invoice_id - deve retornar apenas pagamentos da invoice especificada"""
        response = self.client.get(reverse("financial_get_all"), {"invoice_id": self.invoice1.id})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos da invoice1
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["invoice_id"], self.invoice1.id)

    def test_get_all_view_with_invoice_name_filter(self):
        """Testa filtro por nome da invoice - deve retornar apenas pagamentos da invoice com o termo"""
        response = self.client.get(reverse("financial_get_all"), {"invoice": "Teste 1"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos da invoice1
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertIn("Teste 1", payment["invoice_name"])

    def test_get_all_view_with_date_filters(self):
        """Testa filtros por data - deve retornar pagamentos no intervalo especificado"""
        base_date = datetime.now().date()
        filter_date_gte = (base_date - timedelta(days=7)).strftime("%Y-%m-%d")
        filter_date_lte = (base_date + timedelta(days=7)).strftime("%Y-%m-%d")

        response = self.client.get(reverse("financial_get_all"), {
            "date__gte": filter_date_gte,
            "date__lte": filter_date_lte
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar pagamentos no intervalo
        self.assertGreater(len(data["data"]["data"]), 0)

    def test_get_all_view_with_payment_date_filters(self):
        """Testa filtros por data de pagamento - deve retornar pagamentos no intervalo especificado"""
        base_date = datetime.now().date()
        filter_date_gte = (base_date + timedelta(days=5)).strftime("%Y-%m-%d")
        filter_date_lte = (base_date + timedelta(days=20)).strftime("%Y-%m-%d")

        response = self.client.get(reverse("financial_get_all"), {
            "payment_date__gte": filter_date_gte,
            "payment_date__lte": filter_date_lte
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar pagamentos no intervalo de payment_date
        self.assertGreater(len(data["data"]["data"]), 0)

    def test_get_all_view_with_fixed_filter_true(self):
        """Testa filtro por fixed=true - deve retornar apenas pagamentos fixos"""
        response = self.client.get(reverse("financial_get_all"), {"fixed": "true"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos fixos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertTrue(payment["fixed"])

    def test_get_all_view_with_fixed_filter_false(self):
        """Testa filtro por fixed=false - deve retornar apenas pagamentos não fixos"""
        response = self.client.get(reverse("financial_get_all"), {"fixed": "false"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos não fixos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertFalse(payment["fixed"])

    def test_get_all_view_with_active_filter_true(self):
        """Testa filtro por active=true - deve retornar apenas pagamentos ativos"""
        response = self.client.get(reverse("financial_get_all"), {"active": "true"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos ativos
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertTrue(payment["active"])

    def test_get_all_view_with_active_filter_false(self):
        """Testa filtro por active=false - deve retornar apenas pagamentos inativos"""
        response = self.client.get(reverse("financial_get_all"), {"active": "false"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento inativo
        self.assertEqual(len(data["data"]["data"]), 1)

        for payment in data["data"]["data"]:
            self.assertFalse(payment["active"])

    def test_get_all_view_with_multiple_filters(self):
        """Testa combinação de múltiplos filtros"""
        response = self.client.get(reverse("financial_get_all"), {
            "status": "open",
            "type": Payment.TYPE_DEBIT,
            "fixed": "false",
            "active": "true"
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos (débitos abertos não fixos e ativos)
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_OPEN)
            self.assertEqual(payment["type"], Payment.TYPE_DEBIT)
            self.assertFalse(payment["fixed"])
            self.assertTrue(payment["active"])

    def test_get_all_view_with_pagination(self):
        """Testa paginação dos resultados"""
        response = self.client.get(reverse("financial_get_all"), {"page": "1", "page_size": "2"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos na primeira página
        self.assertEqual(len(data["data"]["data"]), 2)
        self.assertEqual(data["data"]["current_page"], 1)
        self.assertEqual(data["data"]["page_size"], "2")

    def test_get_all_view_tags_structure(self):
        """Testa estrutura das tags nos dados retornados"""
        response = self.client.get(reverse("financial_get_all"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Encontrar pagamento com tags
        payment_with_tags = None
        for payment in data["data"]["data"]:
            if payment["tags"]:
                payment_with_tags = payment
                break

        self.assertIsNotNone(payment_with_tags)
        tags = payment_with_tags["tags"]

        # Verificar estrutura das tags
        self.assertIsInstance(tags, list)
        if tags:
            tag = tags[0]
            expected_tag_fields = ["id", "name", "color", "is_budget"]
            for field in expected_tag_fields:
                self.assertIn(field, tag)

            # Verificar se tags de budget têm prefixo "#"
            for tag in tags:
                if tag["is_budget"]:
                    self.assertTrue(tag["name"].startswith("# "))

    def test_get_all_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.get(reverse("financial_get_all"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_all_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.get(reverse("financial_get_all"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_all_view_error_wrong_method_post(self):
        """Testa erro da view com método POST - deve retornar erro 405"""
        response = self.client.post(reverse("financial_get_all"))

        self.assertEqual(response.status_code, 405)

    def test_get_all_view_edge_case_empty_database(self):
        """Testa comportamento com banco de dados vazio para o usuário"""
        # Deletar todos os pagamentos do usuário
        Payment.objects.filter(user__username="test").delete()

        response = self.client.get(reverse("financial_get_all"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar lista vazia
        self.assertEqual(len(data["data"]["data"]), 0)

    def test_get_all_view_edge_case_invalid_date_filter(self):
        """Testa filtro com data inválida - deve usar data padrão"""
        response = self.client.get(reverse("financial_get_all"), {"date__gte": "data-invalida"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Data inválida usa padrão 2018-01-01, deve retornar todos
        self.assertEqual(len(data["data"]["data"]), 4)

    def test_get_all_view_edge_case_special_characters_in_name_filter(self):
        """Testa edge case com caracteres especiais no filtro de nome"""
        # Criar pagamento com caracteres especiais
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento com ñ e ç",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            user=User.objects.get(username="test"),
            invoice=self.invoice1
        )

        response = self.client.get(reverse("financial_get_all"), {"name__icontains": "ñ"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve encontrar o pagamento com caractere especial
        self.assertEqual(len(data["data"]["data"]), 1)
        self.assertIn("ñ", data["data"]["data"][0]["name"])

    def test_get_all_view_edge_case_very_large_page_size(self):
        """Testa edge case com page_size muito grande"""
        response = self.client.get(reverse("financial_get_all"), {"page_size": "1000"})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar todos os pagamentos em uma página
        self.assertEqual(len(data["data"]["data"]), 4)
        self.assertEqual(data["data"]["page_size"], "1000")

    def test_get_all_view_value_conversion(self):
        """Testa conversão do valor Decimal para float"""
        response = self.client.get(reverse("financial_get_all"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        for payment in data["data"]["data"]:
            # Valor deve ser float, não Decimal
            self.assertIsInstance(payment["value"], float)
            # Verificar se o valor foi convertido corretamente
            original_payment = Payment.objects.get(id=payment["id"])
            self.assertEqual(payment["value"], float(original_payment.value))
