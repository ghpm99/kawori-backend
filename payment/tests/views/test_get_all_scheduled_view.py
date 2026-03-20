import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from payment.models import Payment


class GetAllScheduledViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        # Criar usuário com permissão financial
        user = User.objects.create_superuser(
            username="test", email="test@test.com", password="123"
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        # Criar usuário sem permissão para testes de acesso negado
        normal_user = User.objects.create_user(
            username="normal", email="normal@normal.com", password="123"
        )

        # Criar pagamentos de teste para o usuário com permissão
        base_date = datetime.now().date()

        # Payment 1: débito aberto, data recente
        cls.payment_1 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Teste 1",
            description="Descrição do pagamento 1",
            date=base_date,
            payment_date=base_date + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.50"),
            status=Payment.STATUS_OPEN,
            user=user,
        )

        # Payment 2: crédito done, data antiga
        cls.payment_2 = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Teste 2",
            description="Descrição do pagamento 2",
            date=base_date - timedelta(days=10),
            payment_date=base_date - timedelta(days=5),
            installments=3,
            fixed=True,
            active=True,
            value=Decimal("200.75"),
            status=Payment.STATUS_DONE,
            user=user,
        )

        # Payment 3: débito aberto, parcelado
        cls.payment_3 = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Parcelado Teste",
            description="Descrição do pagamento 3",
            date=base_date - timedelta(days=5),
            payment_date=base_date + timedelta(days=15),
            installments=12,
            fixed=False,
            active=True,
            value=Decimal("150.00"),
            status=Payment.STATUS_OPEN,
            user=user,
        )

        # Payment 4: crédito aberto, inativo
        cls.payment_4 = Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Pagamento Inativo",
            description="Descrição do pagamento 4",
            date=base_date - timedelta(days=20),
            payment_date=base_date + timedelta(days=30),
            installments=1,
            fixed=True,
            active=False,
            value=Decimal("75.25"),
            status=Payment.STATUS_OPEN,
            user=user,
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

    def test_get_all_scheduled_view_success_without_filters(self):
        """Testa sucesso da view sem filtros - deve retornar todos os pagamentos do usuário"""
        response = self.client.get(reverse("financial_get_all_scheduled"))

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
        expected_fields = [
            "id",
            "status",
            "type",
            "name",
            "date",
            "installments",
            "payment_date",
            "fixed",
            "value",
        ]
        for field in expected_fields:
            self.assertIn(field, payment_data)

    def test_get_all_scheduled_view_with_status_filter_open(self):
        """Testa filtro por status 'open' - deve retornar apenas pagamentos abertos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "open"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos abertos
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_OPEN)

    def test_get_all_scheduled_view_with_status_filter_done(self):
        """Testa filtro por status 'done' - deve retornar apenas pagamentos concluídos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "done"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento concluído
        self.assertEqual(len(data["data"]["data"]), 1)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_DONE)

    def test_get_all_scheduled_view_with_status_filter_all(self):
        """Testa filtro por status 'all' - deve retornar todos os pagamentos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "all"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar todos os 4 pagamentos
        self.assertEqual(len(data["data"]["data"]), 4)

    def test_get_all_scheduled_view_with_status_filter_numeric_0(self):
        """Testa filtro por status numérico '0' - deve retornar pagamentos abertos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "0"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos abertos
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_OPEN)

    def test_get_all_scheduled_view_with_status_filter_numeric_1(self):
        """Testa filtro por status numérico '1' - deve retornar pagamentos concluídos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "1"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento concluído
        self.assertEqual(len(data["data"]["data"]), 1)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_DONE)

    def test_get_all_scheduled_view_with_status_filter_invalid(self):
        """Testa filtro por status inválido - deve retornar todos os pagamentos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"status": "invalid"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Status inválido não filtra, retorna todos
        self.assertEqual(len(data["data"]["data"]), 4)

    def test_get_all_scheduled_view_with_type_filter_debit(self):
        """Testa filtro por tipo 'debit' - deve retornar apenas débitos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"type": Payment.TYPE_DEBIT}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 débitos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["type"], Payment.TYPE_DEBIT)

    def test_get_all_scheduled_view_with_type_filter_credit(self):
        """Testa filtro por tipo 'credit' - deve retornar apenas créditos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"type": Payment.TYPE_CREDIT}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 créditos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["type"], Payment.TYPE_CREDIT)

    def test_get_all_scheduled_view_with_name_filter(self):
        """Testa filtro por nome (case insensitive) - deve retornar pagamentos com o termo"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"name__icontains": "teste"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos com "teste" no nome
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertIn("teste", payment["name"].lower())

    def test_get_all_scheduled_view_with_name_filter_empty_result(self):
        """Testa filtro por nome que não retorna resultados"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"name__icontains": "inexistente"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Não deve retornar nenhum pagamento
        self.assertEqual(len(data["data"]["data"]), 0)

    def test_get_all_scheduled_view_with_date_gte_filter(self):
        """Testa filtro por data mínima - deve retornar pagamentos a partir da data especificada"""
        base_date = datetime.now().date()
        filter_date = (base_date - timedelta(days=7)).strftime("%Y-%m-%d")

        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"date__gte": filter_date}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos (payment_1 e payment_3)
        self.assertEqual(len(data["data"]["data"]), 2)

    def test_get_all_scheduled_view_with_date_lte_filter(self):
        """Testa filtro por data máxima - deve retornar pagamentos até a data especificada"""
        base_date = datetime.now().date()
        filter_date = (base_date - timedelta(days=7)).strftime("%Y-%m-%d")

        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"date__lte": filter_date}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos (payment_2 e payment_4)
        self.assertEqual(len(data["data"]["data"]), 2)

    def test_get_all_scheduled_view_with_invalid_date_filter(self):
        """Testa filtro com data inválida - deve usar data padrão"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"date__gte": "data-invalida"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Data inválida usa padrão 2018-01-01, deve retornar todos
        self.assertEqual(len(data["data"]["data"]), 4)

    def test_get_all_scheduled_view_with_installments_filter(self):
        """Testa filtro por número de parcelas"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"installments": "1"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos com 1 parcela
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["installments"], 1)

    def test_get_all_scheduled_view_with_payment_date_gte_filter(self):
        """Testa filtro por data de pagamento mínima"""
        base_date = datetime.now().date()
        filter_date = (base_date + timedelta(days=10)).strftime("%Y-%m-%d")

        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"payment_date__gte": filter_date}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos (payment_3 e payment_4)
        self.assertEqual(len(data["data"]["data"]), 2)

    def test_get_all_scheduled_view_with_payment_date_lte_filter(self):
        """Testa filtro por data de pagamento máxima"""
        base_date = datetime.now().date()
        filter_date = base_date.strftime("%Y-%m-%d")

        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"payment_date__lte": filter_date}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento (payment_2)
        self.assertEqual(len(data["data"]["data"]), 1)

    def test_get_all_scheduled_view_with_fixed_filter_true(self):
        """Testa filtro por fixed=true - deve retornar apenas pagamentos fixos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"fixed": "true"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos fixos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertTrue(payment["fixed"])

    def test_get_all_scheduled_view_with_fixed_filter_false(self):
        """Testa filtro por fixed=false - deve retornar apenas pagamentos não fixos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"fixed": "false"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos não fixos
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertFalse(payment["fixed"])

    def test_get_all_scheduled_view_with_active_filter_true(self):
        """Testa filtro por active=true - deve retornar apenas pagamentos ativos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"active": "true"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 3 pagamentos ativos
        self.assertEqual(len(data["data"]["data"]), 3)

        for payment in data["data"]["data"]:
            self.assertTrue(payment["active"])

    def test_get_all_scheduled_view_with_active_filter_false(self):
        """Testa filtro por active=false - deve retornar apenas pagamentos inativos"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"active": "false"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 1 pagamento inativo
        self.assertEqual(len(data["data"]["data"]), 1)

        for payment in data["data"]["data"]:
            self.assertFalse(payment["active"])

    def test_get_all_scheduled_view_with_multiple_filters(self):
        """Testa combinação de múltiplos filtros"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"),
            {"status": "open", "type": Payment.TYPE_DEBIT, "fixed": "false"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos (débitos abertos não fixos)
        self.assertEqual(len(data["data"]["data"]), 2)

        for payment in data["data"]["data"]:
            self.assertEqual(payment["status"], Payment.STATUS_OPEN)
            self.assertEqual(payment["type"], Payment.TYPE_DEBIT)
            self.assertFalse(payment["fixed"])

    def test_get_all_scheduled_view_with_pagination(self):
        """Testa paginação dos resultados"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page": "1", "page_size": "2"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos na primeira página
        self.assertEqual(len(data["data"]["data"]), 2)
        self.assertEqual(data["data"]["page"], 1)
        self.assertEqual(data["data"]["page_size"], 2)
        self.assertEqual(data["data"]["total"], 4)
        self.assertEqual(data["data"]["pages"], 2)

    def test_get_all_scheduled_view_with_pagination_second_page(self):
        """Testa segunda página da paginação"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page": "2", "page_size": "2"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar 2 pagamentos na segunda página
        self.assertEqual(len(data["data"]["data"]), 2)
        self.assertEqual(data["data"]["page"], 2)
        self.assertEqual(data["data"]["page_size"], 2)

    def test_get_all_scheduled_view_with_default_pagination(self):
        """Testa paginação com valores padrão"""
        response = self.client.get(reverse("financial_get_all_scheduled"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # page_size padrão deve ser 10
        self.assertEqual(data["data"]["page_size"], "10")
        self.assertEqual(data["data"]["current_page"], 1)

    def test_get_all_scheduled_view_ordering(self):
        """Testa ordenação dos resultados por payment_date e id"""
        response = self.client.get(reverse("financial_get_all_scheduled"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        payments = data["data"]["data"]

        # Verificar se está ordenado por payment_date, depois por id
        for i in range(len(payments) - 1):
            current_date = datetime.strptime(
                payments[i]["payment_date"], "%Y-%m-%d"
            ).date()
            next_date = datetime.strptime(
                payments[i + 1]["payment_date"], "%Y-%m-%d"
            ).date()

            if current_date == next_date:
                # Se datas forem iguais, ordenar por id
                self.assertLess(payments[i]["id"], payments[i + 1]["id"])
            else:
                # Senão, ordenar por data
                self.assertLessEqual(current_date, next_date)

    def test_get_all_scheduled_view_value_conversion(self):
        """Testa conversão do valor Decimal para float"""
        response = self.client.get(reverse("financial_get_all_scheduled"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        for payment in data["data"]["data"]:
            # Valor deve ser float, não Decimal
            self.assertIsInstance(payment["value"], float)
            # Verificar se o valor foi convertido corretamente
            original_payment = Payment.objects.get(id=payment["id"])
            self.assertEqual(payment["value"], float(original_payment.value))

    def test_get_all_scheduled_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.get(reverse("financial_get_all_scheduled"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_all_scheduled_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.get(reverse("financial_get_all_scheduled"))

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_all_scheduled_view_empty_database(self):
        """Testa comportamento com banco de dados vazio para o usuário"""
        # Deletar todos os pagamentos do usuário
        Payment.objects.filter(user__username="test").delete()

        response = self.client.get(reverse("financial_get_all_scheduled"))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar lista vazia
        self.assertEqual(len(data["data"]["data"]), 0)
        self.assertEqual(data["data"]["total"], 0)
        self.assertEqual(data["data"]["pages"], 0)

    def test_get_all_scheduled_view_edge_case_very_large_page_size(self):
        """Testa edge case com page_size muito grande"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page_size": "1000"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar todos os 4 pagamentos em uma página
        self.assertEqual(len(data["data"]["data"]), 4)
        self.assertEqual(data["data"]["page_size"], "1000")
        self.assertEqual(data["data"]["current_page"], 1)

    def test_get_all_scheduled_view_edge_case_page_zero(self):
        """Testa edge case com página igual a zero"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page": "0"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve tratar como página 1
        self.assertEqual(data["data"]["current_page"], 1)

    def test_get_all_scheduled_view_edge_case_negative_page(self):
        """Testa edge case com página negativa"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page": "-1"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve tratar como página 1
        self.assertEqual(data["data"]["current_page"], 1)

    def test_get_all_scheduled_view_edge_case_page_beyond_results(self):
        """Testa edge case com página além dos resultados"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"page": "10", "page_size": "2"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar lista vazia
        self.assertEqual(len(data["data"]["data"]), 0)

    def test_get_all_scheduled_view_edge_case_special_characters_in_name_filter(self):
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
        )

        response = self.client.get(
            reverse("financial_get_all_scheduled"), {"name__icontains": "ñ"}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve encontrar o pagamento com caractere especial
        self.assertEqual(len(data["data"]["data"]), 1)
        self.assertIn("ñ", data["data"]["data"][0]["name"])

    def test_get_all_scheduled_view_edge_case_empty_string_filters(self):
        """Testa edge case com filtros sendo strings vazias"""
        response = self.client.get(
            reverse("financial_get_all_scheduled"),
            {"status": "", "type": "", "name__icontains": ""},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Strings vazias não devem filtrar, retornar todos
        self.assertEqual(len(data["data"]["data"]), 4)

    def test_get_all_scheduled_view_edge_case_boolean_filters_with_variations(self):
        """Testa edge case com filtros booleanos recebendo variações de strings"""
        # Testar diferentes representações de verdadeiro/falso
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]

        for filter_value, expected_bool in test_cases:
            with self.subTest(filter_value=filter_value):
                response = self.client.get(
                    reverse("financial_get_all_scheduled"), {"fixed": filter_value}
                )

                self.assertEqual(response.status_code, 200)
                data = json.loads(response.content)

                for payment in data["data"]["data"]:
                    self.assertEqual(payment["fixed"], expected_bool)
