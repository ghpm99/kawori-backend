import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from payment.models import Payment

class GetCSVMappingViewTestCase(TestCase):
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

    def test_get_csv_mapping_success_with_known_headers(self):
        """Testa sucesso da view com cabeçalhos CSV conhecidos - deve retornar mapeamento correto"""
        headers = ["data", "valor", "identificador", "descrição"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 4)

        # Verificar mapeamento correto dos cabeçalhos conhecidos
        expected_mappings = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "identificador", "system_field": "reference"},
            {"csv_column": "descrição", "system_field": "description"}
        ]

        self.assertEqual(data["data"], expected_mappings)

    def test_get_csv_mapping_success_with_mixed_case_headers(self):
        """Testa sucesso da view com cabeçalhos em casos mistos - deve normalizar e mapear corretamente"""
        headers = ["Data", "VALOR", "Identificador", "DESCRIÇÃO"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Verificar se manteve o caso original mas mapeou corretamente
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            self.assertIn(mapping["system_field"], ["date", "value", "reference", "description"])

    def test_get_csv_mapping_success_with_headers_with_spaces(self):
        """Testa sucesso da view com cabeçalhos com espaços - deve remover espaços e mapear corretamente"""
        headers = [" data ", "  valor  ", "  identificador ", "descrição "]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Verificar se manteve os espaços originais no csv_column mas mapeou corretamente
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            self.assertIn(mapping["system_field"], ["date", "value", "reference", "description"])

    def test_get_csv_mapping_success_with_unknown_headers(self):
        """Testa sucesso da view com cabeçalhos desconhecidos - deve mapear como 'ignore'"""
        headers = ["coluna_desconhecida", "campo_inexistente", "header_nao_mapeado"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Todos devem ser mapeados como 'ignore'
        for mapping in data["data"]:
            self.assertEqual(mapping["system_field"], "ignore")
            self.assertIn(mapping["csv_column"], headers)

    def test_get_csv_mapping_success_with_mixed_known_unknown_headers(self):
        """Testa sucesso da view com cabeçalhos conhecidos e desconhecidos misturados"""
        headers = ["data", "coluna_desconhecida", "valor", "campo_inexistente"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Verificar mapeamento misto
        self.assertEqual(data["data"][0]["system_field"], "date")  # data conhecido
        self.assertEqual(data["data"][1]["system_field"], "ignore")  # desconhecido
        self.assertEqual(data["data"][2]["system_field"], "value")  # valor conhecido
        self.assertEqual(data["data"][3]["system_field"], "ignore")  # desconhecido

    def test_get_csv_mapping_success_with_english_headers(self):
        """Testa sucesso da view com cabeçalhos em inglês - deve mapear corretamente"""
        headers = ["date", "title", "amount"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Verificar mapeamento dos cabeçalhos em inglês
        expected_mappings = [
            {"csv_column": "date", "system_field": "date"},
            {"csv_column": "title", "system_field": "description"},
            {"csv_column": "amount", "system_field": "value"}
        ]

        self.assertEqual(data["data"], expected_mappings)

    def test_get_csv_mapping_error_missing_headers(self):
        """Testa erro da view sem o parâmetro headers - deve retornar status 400"""
        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "CSV mapping is required")

    def test_get_csv_mapping_error_empty_headers_list(self):
        """Testa erro da view com lista de headers vazia - deve retornar status 400"""
        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": []}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "CSV mapping is required")

    def test_get_csv_mapping_error_null_headers(self):
        """Testa erro da view com headers nulos - deve retornar status 400"""
        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": None}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "CSV mapping is required")

    def test_get_csv_mapping_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data="json_invalido",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_get_csv_mapping_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_get_csv_mapping"))

        self.assertEqual(response.status_code, 405)

    def test_get_csv_mapping_error_wrong_method_put(self):
        """Testa erro da view com método PUT - deve retornar erro 405"""
        response = self.client.put(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": ["data"]}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 405)

    def test_get_csv_mapping_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": ["data"]}),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_csv_mapping_no_authentication(self):
        """Testa acesso sem autenticação"""
        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": ["data"]}),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_get_csv_mapping_edge_case_single_header(self):
        """Testa edge case com apenas um cabeçalho"""
        headers = ["data"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0], {"csv_column": "data", "system_field": "date"})

    def test_get_csv_mapping_edge_case_many_headers(self):
        """Testa edge case com muitos cabeçalhos"""
        headers = ["data", "valor", "identificador", "descrição", "date", "title", "amount"] * 10

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), len(headers))

        # Verificar se todos os cabeçalhos foram processados
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            self.assertIn(mapping["system_field"], ["date", "value", "reference", "description", "ignore"])

    def test_get_csv_mapping_edge_case_empty_string_headers(self):
        """Testa edge case com cabeçalhos sendo strings vazias"""
        headers = ["", " ", "   ", "data"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Strings vazias devem ser mapeadas como 'ignore'
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            if headers[i].strip() == "":
                self.assertEqual(mapping["system_field"], "ignore")
            else:
                self.assertIn(mapping["system_field"], ["date", "value", "reference", "description", "ignore"])

    def test_get_csv_mapping_edge_case_special_characters_headers(self):
        """Testa edge case com cabeçalhos contendo caracteres especiais"""
        headers = ["dátá", "valór", "identíficadór", "descriçãó"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Todos devem ser mapeados como 'ignore' devido aos caracteres especiais
        for mapping in data["data"]:
            self.assertEqual(mapping["system_field"], "ignore")
            self.assertIn(mapping["csv_column"], headers)

    def test_get_csv_mapping_edge_case_numeric_headers(self):
        """Testa edge case com cabeçalhos numéricos"""
        headers = ["1", "2", "3", "data"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Números devem ser mapeados como 'ignore', exceto 'data'
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            if headers[i] == "data":
                self.assertEqual(mapping["system_field"], "date")
            else:
                self.assertEqual(mapping["system_field"], "ignore")

    def test_get_csv_mapping_edge_case_duplicate_headers(self):
        """Testa edge case com cabeçalhos duplicados"""
        headers = ["data", "data", "valor", "valor"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 4)

        # Deve processar cada duplicata individualmente
        for i, mapping in enumerate(data["data"]):
            self.assertEqual(mapping["csv_column"], headers[i])
            if headers[i] in ["data", "valor"]:
                expected_field = "date" if headers[i] == "data" else "value"
                self.assertEqual(mapping["system_field"], expected_field)

    def test_get_csv_mapping_response_structure(self):
        """Testa estrutura da resposta da view"""
        headers = ["data", "valor"]

        response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": headers}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura da resposta
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        # Verificar estrutura de cada item do mapeamento
        for mapping in data["data"]:
            self.assertIn("csv_column", mapping)
            self.assertIn("system_field", mapping)
            self.assertIsInstance(mapping["csv_column"], str)
            self.assertIsInstance(mapping["system_field"], str)
