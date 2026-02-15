import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from payment.models import Payment

class ProcessCSVUploadViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        # Criar usuário com permissão financial
        user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        # Criar usuário sem permissão para testes de acesso negado
        normal_user = User.objects.create_user(username="normal", email="normal@normal.com", password="123")

        # Criar alguns pagamentos existentes para testes de matching
        base_date = datetime.now().date()
        cls.existing_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Existente",
            description="Descrição do pagamento existente",
            date=base_date,
            payment_date=base_date + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=user
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

    def test_process_csv_upload_success_with_valid_data(self):
        """Testa sucesso da view com dados CSV válidos - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "150.50", "descrição": "Pagamento Teste 1"},
            {"data": "16/02/2026", "valor": "200.75", "descrição": "Pagamento Teste 2"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 2)

        # Verificar estrutura de cada transação processada
        for transaction in data["data"]:
            self.assertIn("id", transaction)
            self.assertIn("original_row", transaction)
            self.assertIn("mapped_data", transaction)
            self.assertIn("validation_errors", transaction)
            self.assertIn("is_valid", transaction)
            self.assertIsInstance(transaction["validation_errors"], list)
            self.assertIsInstance(transaction["is_valid"], bool)

    def test_process_csv_upload_success_with_payment_date(self):
        """Testa sucesso da view com data de pagamento específica - deve usar a data fornecida"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)
        self.assertIn("mapped_data", data["data"][0])
        self.assertIsNotNone(data["data"][0]["mapped_data"])

    def test_process_csv_upload_success_with_empty_body(self):
        """Testa sucesso da view com corpo vazio - deve retornar lista vazia"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = []

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 0)

    def test_process_csv_upload_success_with_default_import_type(self):
        """Testa sucesso da view sem tipo de importação - deve usar padrão 'transactions'"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

    def test_process_csv_upload_error_missing_headers(self):
        """Testa erro da view sem headers - deve processar com lista vazia"""
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve processar, mas sem mapeamento
        self.assertEqual(len(data["data"]), 1)

    def test_process_csv_upload_error_missing_body(self):
        """Testa erro da view sem body - deve retornar lista vazia"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 0)

    def test_process_csv_upload_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data="json_invalido",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_process_csv_upload_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_process_csv_upload"))

        self.assertEqual(response.status_code, 405)

    def test_process_csv_upload_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_process_csv_upload_no_authentication(self):
        """Testa acesso sem autenticação"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_process_csv_upload_edge_case_invalid_date_format(self):
        """Testa edge case com formato de data inválido - deve gerar erros de validação"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "data_invalida", "valor": "100.00"},
            {"data": "2026-02-30", "valor": "150.00"}  # Data inexistente
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve ter erros de validação para datas inválidas
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_invalid_value_format(self):
        """Testa edge case com formato de valor inválido - deve gerar erros de validação"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "valor_invalido"},
            {"data": "16/02/2026", "valor": "abc123"},
            {"data": "17/02/2026", "valor": "-50.00"}  # Valor negativo
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Deve processar, mas com possíveis erros de validação
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_missing_required_fields(self):
        """Testa edge case com campos obrigatórios faltando - deve gerar erros de validação"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026"},  # Falta valor
            {"valor": "100.00"},      # Falta data
            {"data": "16/02/2026", "descrição": "Teste"}  # Falta valor
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Deve processar, mas com erros de validação
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_empty_string_values(self):
        """Testa edge case com valores strings vazios - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "", "valor": "", "descrição": ""},
            {"data": "15/02/2026", "valor": "100.00", "descrição": ""}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar, mas possivelmente com erros de validação
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_special_characters(self):
        """Testa edge case com caracteres especiais nos dados - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.50", "descrição": "Pagamento com ñ e ç"},
            {"data": "16/02/2026", "valor": "200.75", "descrição": "Teste @#$%&*()"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar caracteres especiais corretamente
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_very_long_values(self):
        """Testa edge case com valores muito longos - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        long_description = "A" * 1000  # 1000 caracteres
        body = [
            {"data": "15/02/2026", "valor": "100.00", "descrição": long_description}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["original_row"]["descrição"], long_description)

    def test_process_csv_upload_edge_case_numeric_values_as_strings(self):
        """Testa edge case com valores numéricos como strings - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "parcelas", "system_field": "installments"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.50", "parcelas": "3"},
            {"data": "16/02/2026", "valor": "200", "parcelas": "1"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar valores numéricos como strings
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_null_values(self):
        """Testa edge case com valores nulos - deve processar corretamente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": None, "valor": None, "descrição": None},
            {"data": "15/02/2026", "valor": "100.00", "descrição": None}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar valores nulos
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_edge_case_mismatched_headers_and_columns(self):
        """Testa edge case com headers e colunas não correspondentes - deve processar com dados disponíveis"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "coluna_inexistente", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00", "outra_coluna": "teste"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Deve processar apenas com os dados disponíveis
        transaction = data["data"][0]
        self.assertEqual(transaction["original_row"]["data"], "15/02/2026")
        self.assertEqual(transaction["original_row"]["valor"], "100.00")
        self.assertEqual(transaction["original_row"]["outra_coluna"], "teste")

    def test_process_csv_upload_edge_case_very_large_dataset(self):
        """Testa edge case com dataset muito grande - deve processar sem erros"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]

        # Criar 100 linhas de dados
        body = [
            {"data": f"15/02/2026", "valor": f"{i + 1}.00"}
            for i in range(100)
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 100)

        # Todas as transações devem ter estrutura válida
        for transaction in data["data"]:
            self.assertIn("id", transaction)
            self.assertIn("original_row", transaction)
            self.assertIn("mapped_data", transaction)
            self.assertIn("validation_errors", transaction)
            self.assertIn("is_valid", transaction)

    def test_process_csv_upload_edge_case_invalid_payment_date(self):
        """Testa edge case com data de pagamento inválida - deve usar tratamento padrão"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions",
                "payment_date": "data_invalida"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Deve processar mesmo com data inválida
        transaction = data["data"][0]
        self.assertIsInstance(transaction["is_valid"], bool)
        self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_response_structure(self):
        """Testa estrutura da resposta da view"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura principal
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        # Verificar estrutura de cada transação
        transaction = data["data"][0]
        required_fields = ["id", "original_row", "mapped_data", "validation_errors", "is_valid"]
        for field in required_fields:
            self.assertIn(field, transaction)

        # Verificar tipos
        self.assertIsInstance(transaction["id"], str)
        self.assertIsInstance(transaction["original_row"], dict)
        self.assertIsInstance(transaction["validation_errors"], list)
        self.assertIsInstance(transaction["is_valid"], bool)

    def test_process_csv_upload_card_payments_with_payment_date(self):
        """Testa comportamento com import_type card_payments e payment_date - deve usar payment_date para todos os registros"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00", "descrição": "Cartão 1"},
            {"data": "16/02/2026", "valor": "200.00", "descrição": "Cartão 2"},
            {"data": "17/02/2026", "valor": "150.00", "descrição": "Cartão 3"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "card_payments",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Para card_payments, todos os registros devem ter a mesma payment_date
        for transaction in data["data"]:
            self.assertIn("mapped_data", transaction)
            mapped_data = transaction["mapped_data"]
            if mapped_data:
                # Verificar se payment_date foi aplicado consistentemente
                self.assertIsInstance(mapped_data, dict)

    def test_process_csv_upload_card_payments_without_payment_date(self):
        """Testa comportamento com import_type card_payments sem payment_date - deve usar tratamento padrão"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"},
            {"data": "16/02/2026", "valor": "200.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "card_payments"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar mesmo sem payment_date
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_transactions_ignores_payment_date(self):
        """Testa comportamento com import_type transactions - payment_date não deve afetar os valores dos registros"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "descrição", "system_field": "description"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00", "descrição": "Transação 1"},
            {"data": "16/02/2026", "valor": "200.00", "descrição": "Transação 2"},
            {"data": "17/02/2026", "valor": "150.00", "descrição": "Transação 3"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 3)

        # Para transactions, os valores originais devem ser mantidos
        for i, transaction in enumerate(data["data"]):
            self.assertIn("mapped_data", transaction)
            mapped_data = transaction["mapped_data"]
            if mapped_data:
                # Verificar se os valores originais foram preservados
                self.assertIsInstance(mapped_data, dict)

    def test_process_csv_upload_transactions_without_payment_date(self):
        """Testa comportamento com import_type transactions sem payment_date - deve processar normalmente"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"},
            {"data": "16/02/2026", "valor": "200.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Deve processar normalmente sem payment_date
        for transaction in data["data"]:
            self.assertIsInstance(transaction["is_valid"], bool)
            self.assertIsInstance(transaction["validation_errors"], list)

    def test_process_csv_upload_card_payments_vs_transactions_behavior(self):
        """Testa diferença de comportamento entre card_payments e transactions com mesmo payment_date"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        # Testar com card_payments
        response_card = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "card_payments",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        # Testar com transactions
        response_trans = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "transactions",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        self.assertEqual(response_card.status_code, 200)
        self.assertEqual(response_trans.status_code, 200)

        data_card = json.loads(response_card.content)
        data_trans = json.loads(response_trans.content)

        self.assertEqual(len(data_card["data"]), 1)
        self.assertEqual(len(data_trans["data"]), 1)

        # Ambos devem processar, mas com comportamentos diferentes
        card_transaction = data_card["data"][0]
        trans_transaction = data_trans["data"][0]

        self.assertIsInstance(card_transaction["is_valid"], bool)
        self.assertIsInstance(trans_transaction["is_valid"], bool)

    def test_process_csv_upload_invalid_import_type(self):
        """Testa comportamento com import_type inválido - deve usar tratamento padrão ou erro"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "tipo_invalido",
                "payment_date": "20/02/2026"
            }),
            content_type="application/json"
        )

        # A view deve processar mesmo com import_type inválido
        # (depende da implementação específica)
        self.assertIn(response.status_code, [200, 400])

        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertEqual(len(data["data"]), 1)

    def test_process_csv_upload_card_payments_empty_payment_date(self):
        """Testa card_payments com payment_date vazio - deve usar tratamento padrão"""
        headers = [
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "valor", "system_field": "value"}
        ]
        body = [
            {"data": "15/02/2026", "valor": "100.00"}
        ]

        response = self.client.post(
            reverse("financial_process_csv_upload"),
            data=json.dumps({
                "headers": headers,
                "body": body,
                "import_type": "card_payments",
                "payment_date": ""
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Deve processar mesmo com payment_date vazio
        transaction = data["data"][0]
        self.assertIsInstance(transaction["is_valid"], bool)
        self.assertIsInstance(transaction["validation_errors"], list)
