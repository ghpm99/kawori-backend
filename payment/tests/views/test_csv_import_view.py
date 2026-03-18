import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from budget.models import Budget
from invoice.models import Invoice
from payment.models import ImportedPayment, Payment
from tag.models import Tag


class CSVImportViewTestCase(TestCase):
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
        cls.tag1 = Tag.objects.create(name="Tag Import 1", color="#FF0000", user=user)
        cls.tag2 = Tag.objects.create(name="Tag Import 2", color="#00FF00", user=user)
        cls.budget_tag = Tag.objects.create(name="Budget Import", color="#0000FF", user=user)

        # Criar invoice para testes
        cls.invoice = Invoice.objects.create(
            name="Fatura Import Teste",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user
        )

        # Criar ImportedPayments para testes
        cls.imported_payment_1 = ImportedPayment.objects.create(
            user=user,
            reference="ref_import_1",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Importação Teste 1",
            raw_description="Descrição importação 1",
            raw_date="2026-02-15",
            raw_payment_date="2026-02-20",
            raw_installments=1,
            raw_value=Decimal("100.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING
        )

        cls.imported_payment_2 = ImportedPayment.objects.create(
            user=user,
            reference="ref_import_2",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_MERGE,
            raw_type=Payment.TYPE_CREDIT,
            raw_name="Importação Teste 2",
            raw_description="Descrição importação 2",
            raw_date="2026-02-16",
            raw_payment_date="2026-02-21",
            raw_installments=1,
            raw_value=Decimal("200.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING
        )

        cls.imported_payment_3 = ImportedPayment.objects.create(
            user=user,
            reference="ref_import_3",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Importação Teste 3",
            raw_description="Descrição importação 3",
            raw_date="2026-02-17",
            raw_payment_date="2026-02-22",
            raw_installments=1,
            raw_value=Decimal("150.00"),
            status=ImportedPayment.IMPORT_STATUS_PROCESSING  # Não editável
        )

        # Criar ImportedPayment para usuário normal (não deve ser acessível)
        cls.imported_payment_normal = ImportedPayment.objects.create(
            user=normal_user,
            reference="ref_import_normal",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Importação Normal",
            raw_value=Decimal("50.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING
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

    def test_csv_import_view_success_with_budget_tags(self):
        """Testa sucesso da view com tags que incluem budget - deve processar importações"""
        # Adicionar budget tag a uma tag existente
        # (Simulando que a tag já tem budget associado)
        
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                },
                {
                    "import_payment_id": self.imported_payment_2.id,
                    "tags": [self.tag2.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertIn("total", data)
        self.assertEqual(data["msg"], "Importação iniciada")
        self.assertEqual(data["total"], 2)

        # Verificar se as tags foram associadas
        self.imported_payment_1.refresh_from_db()
        self.imported_payment_2.refresh_from_db()

        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_QUEUED)
        self.assertEqual(self.imported_payment_2.status, ImportedPayment.IMPORT_STATUS_QUEUED)

        # Verificar se as tags foram definidas
        tags_1 = list(self.imported_payment_1.raw_tags.all())
        tags_2 = list(self.imported_payment_2.raw_tags.all())

        self.assertEqual(len(tags_1), 2)
        self.assertEqual(len(tags_2), 2)

    def test_csv_import_view_success_without_budget_tags(self):
        """Testa sucesso da view sem budget tags - deve pular importações"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id]  # Sem budget tag
                },
                {
                    "import_payment_id": self.imported_payment_2.id,
                    "tags": [self.tag2.id]  # Sem budget tag
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertIn("total", data)
        self.assertEqual(data["msg"], "Importação iniciada")
        self.assertEqual(data["total"], 0)  # Nenhum processado por falta de budget tag

        # Verificar que o status não mudou
        self.imported_payment_1.refresh_from_db()
        self.imported_payment_2.refresh_from_db()

        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_PENDING)
        self.assertEqual(self.imported_payment_2.status, ImportedPayment.IMPORT_STATUS_PENDING)

    def test_csv_import_view_success_mixed_budget_tags(self):
        """Testa sucesso da view com mix de com/sem budget tags - deve processar apenas os com budget"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]  # Com budget
                },
                {
                    "import_payment_id": self.imported_payment_2.id,
                    "tags": [self.tag2.id]  # Sem budget
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 1)  # Apenas o primeiro com budget tag

        # Verificar que apenas o primeiro foi processado
        self.imported_payment_1.refresh_from_db()
        self.imported_payment_2.refresh_from_db()

        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_QUEUED)
        self.assertEqual(self.imported_payment_2.status, ImportedPayment.IMPORT_STATUS_PENDING)

    def test_csv_import_view_success_empty_tags_list(self):
        """Testa sucesso da view com lista de tags vazia - deve pular importações"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": []  # Lista vazia
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)  # Nenhum processado

        # Verificar que o status não mudou
        self.imported_payment_1.refresh_from_db()
        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_PENDING)

    def test_csv_import_view_skip_non_editable_imported_payment(self):
        """Testa view pulando ImportedPayment não editável"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_3.id,  # Status PROCESSING
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)  # Pulou por não ser editável

        # Verificar que o status não mudou
        self.imported_payment_3.refresh_from_db()
        self.assertEqual(self.imported_payment_3.status, ImportedPayment.IMPORT_STATUS_PROCESSING)

    def test_csv_import_view_skip_nonexistent_imported_payment(self):
        """Testa view pulando ImportedPayment inexistente"""
        import_data = {
            "data": [
                {
                    "import_payment_id": 99999,  # Não existe
                    "tags": [self.tag1.id, self.budget_tag.id]
                },
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 1)  # Apenas o existente foi processado

        # Verificar que o existente foi processado
        self.imported_payment_1.refresh_from_db()
        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_QUEUED)

    def test_csv_import_view_skip_imported_payment_from_other_user(self):
        """Testa view pulando ImportedPayment de outro usuário"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_normal.id,  # De outro usuário
                    "tags": [self.tag1.id, self.budget_tag.id]
                },
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 1)  # Apenas o do usuário atual foi processado

        # Verificar que o do usuário atual foi processado
        self.imported_payment_1.refresh_from_db()
        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_QUEUED)

    def test_csv_import_view_success_multiple_tags_per_import(self):
        """Testa sucesso da view com múltiplas tags por importação - deve associar todas"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.tag2.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 1)

        # Verificar se todas as tags foram associadas
        self.imported_payment_1.refresh_from_db()
        tags = list(self.imported_payment_1.raw_tags.all())
        self.assertEqual(len(tags), 3)

        tag_names = [tag.name for tag in tags]
        self.assertIn("Tag Import 1", tag_names)
        self.assertIn("Tag Import 2", tag_names)
        self.assertIn("Budget Import", tag_names)

    def test_csv_import_view_error_missing_data_field(self):
        """Testa erro da view sem campo data - deve retornar erro 400"""
        import_data = {
            # Sem campo "data"
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_import_view_error_empty_data_list(self):
        """Testa view com lista data vazia - deve processar zero importações"""
        import_data = {
            "data": []
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertIn("total", data)
        self.assertEqual(data["msg"], "Importação iniciada")
        self.assertEqual(data["total"], 0)

    def test_csv_import_view_error_missing_import_payment_id(self):
        """Testa erro da view sem import_payment_id - deve retornar erro 400"""
        import_data = {
            "data": [
                {
                    "tags": [self.tag1.id, self.budget_tag.id]
                    # Sem import_payment_id
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_import_view_error_missing_tags_field(self):
        """Testa erro da view sem campo tags - deve retornar erro 400"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id
                    # Sem campo tags
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_import_view_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_csv_import_view"),
            data="json_invalido",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_import_view_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_csv_import_view"))

        self.assertEqual(response.status_code, 405)

    def test_csv_import_view_error_wrong_method_put(self):
        """Testa erro da view com método PUT - deve retornar erro 405"""
        response = self.client.put(reverse("financial_csv_import_view"))

        self.assertEqual(response.status_code, 405)

    def test_csv_import_view_error_wrong_method_delete(self):
        """Testa erro da view com método DELETE - deve retornar erro 405"""
        response = self.client.delete(reverse("financial_csv_import_view"))

        self.assertEqual(response.status_code, 405)

    def test_csv_import_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_csv_import_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_csv_import_view_edge_case_invalid_tag_ids(self):
        """Testa edge case com IDs de tags inválidos - deve pular importações"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [99999, 88888]  # Tags não existem
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)  # Nenhuma tag encontrada

        # Verificar que o status não mudou
        self.imported_payment_1.refresh_from_db()
        self.assertEqual(self.imported_payment_1.status, ImportedPayment.IMPORT_STATUS_PENDING)

    def test_csv_import_view_edge_case_tags_from_other_user(self):
        """Testa edge case com tags de outro usuário - deve pular importações"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id]  # Tag do usuário atual
                }
            ]
        }

        # Criar tag para usuário normal
        tag_normal = Tag.objects.create(name="Tag Normal", color="#CCCCCC", user=User.objects.get(username="normal"))

        import_data_normal = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [tag_normal.id]  # Tag de outro usuário
                }
            ]
        }

        # Testar com tag de outro usuário
        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data_normal),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)  # Tag não encontrada para o usuário

    def test_csv_import_view_edge_case_very_large_import_list(self):
        """Testa edge case com lista de importação muito grande - deve processar todos"""
        # Criar muitos ImportedPayments
        user = User.objects.get(username="test")
        imported_payments = []
        
        for i in range(20):
            imported = ImportedPayment.objects.create(
                user=user,
                reference=f"ref_grande_{i}",
                import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
                raw_type=Payment.TYPE_DEBIT,
                raw_name=f"Importação Grande {i}",
                raw_value=Decimal("100.00"),
                status=ImportedPayment.IMPORT_STATUS_PENDING
            )
            imported_payments.append(imported)

        import_data = {
            "data": [
                {
                    "import_payment_id": imported.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
                for imported in imported_payments
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 20)

        # Verificar se todos foram processados
        for imported in imported_payments:
            imported.refresh_from_db()
            self.assertEqual(imported.status, ImportedPayment.IMPORT_STATUS_QUEUED)

    def test_csv_import_view_edge_case_duplicate_import_payment_ids(self):
        """Testa edge case com IDs de importação duplicados - deve processar apenas uma vez"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                },
                {
                    "import_payment_id": self.imported_payment_1.id,  # Duplicado
                    "tags": [self.tag2.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 1)  # Processado apenas uma vez

        # Verificar que o import foi processado (último com mesmo id sobrescreve tags)
        self.imported_payment_1.refresh_from_db()
        tags = list(self.imported_payment_1.raw_tags.all())
        self.assertEqual(len(tags), 2)

        tag_names = [tag.name for tag in tags]
        self.assertIn("Tag Import 2", tag_names)
        self.assertIn("Budget Import", tag_names)

    def test_csv_import_view_response_structure(self):
        """Testa estrutura da resposta da view"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura da resposta
        self.assertIn("msg", data)
        self.assertIn("total", data)
        self.assertIsInstance(data["msg"], str)
        self.assertIsInstance(data["total"], int)

        self.assertEqual(data["msg"], "Importação iniciada")

    def test_csv_import_view_tag_association_verification(self):
        """Testa verificação da associação correta das tags"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id, self.tag2.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verificar associação detalhada das tags
        self.imported_payment_1.refresh_from_db()
        tags = list(self.imported_payment_1.raw_tags.all().order_by("name"))
        
        self.assertEqual(len(tags), 3)
        self.assertEqual(tags[0].name, "Budget Import")
        self.assertEqual(tags[1].name, "Tag Import 1")
        self.assertEqual(tags[2].name, "Tag Import 2")

        # Verificar se as tags são as corretas
        tag_ids = [tag.id for tag in tags]
        self.assertIn(self.tag1.id, tag_ids)
        self.assertIn(self.tag2.id, tag_ids)
        self.assertIn(self.budget_tag.id, tag_ids)

    def test_csv_import_view_returns_skipped_with_reasons(self):
        """Testa que a resposta inclui array skipped com motivos"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": [self.tag1.id]  # Sem budget tag
                },
                {
                    "import_payment_id": self.imported_payment_3.id,  # PROCESSING - não editável
                    "tags": [self.tag1.id, self.budget_tag.id]
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)
        self.assertIn("skipped", data)
        self.assertEqual(len(data["skipped"]), 2)

        reasons = {item["reason"] for item in data["skipped"]}
        self.assertIn("no_budget_tag", reasons)
        self.assertIn("not_editable", reasons)

    def test_csv_import_view_skipped_empty_tags(self):
        """Testa que tags vazias geram skip com reason no_tags"""
        import_data = {
            "data": [
                {
                    "import_payment_id": self.imported_payment_1.id,
                    "tags": []
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["skipped"]), 1)
        self.assertEqual(data["skipped"][0]["reason"], "no_tags")

    def test_csv_import_view_merge_group_tag_propagation(self):
        """Testa que tags são propagadas dentro do merge_group - IOF herda tags do principal"""
        user = User.objects.get(username="test")

        # Criar budget real para a tag
        Budget.objects.get_or_create(
            user=user,
            tag=self.budget_tag,
            defaults={"allocation_percentage": Decimal("10.00")}
        )

        # Pagamento principal com merge_group
        main_imported = ImportedPayment.objects.create(
            user=user,
            reference="ref_discord",
            import_source=ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            merge_group="discord_group",
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Discord",
            raw_value=Decimal("30.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING
        )

        # IOF no mesmo merge_group
        iof_imported = ImportedPayment.objects.create(
            user=user,
            reference="ref_iof_discord",
            import_source=ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            merge_group="discord_group",
            raw_type=Payment.TYPE_DEBIT,
            raw_name="IOF Discord",
            raw_value=Decimal("2.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING
        )

        import_data = {
            "data": [
                {
                    "import_payment_id": main_imported.id,
                    "tags": [self.budget_tag.id, self.tag1.id]  # Tags no principal
                },
                {
                    "import_payment_id": iof_imported.id,
                    "tags": []  # IOF sem tags - deve herdar do merge_group
                }
            ]
        }

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(import_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Ambos devem ser processados - IOF herda tags do principal via merge_group
        self.assertEqual(data["total"], 2)

        main_imported.refresh_from_db()
        iof_imported.refresh_from_db()

        self.assertEqual(main_imported.status, ImportedPayment.IMPORT_STATUS_QUEUED)
        self.assertEqual(iof_imported.status, ImportedPayment.IMPORT_STATUS_QUEUED)

        # Verificar que IOF recebeu as mesmas tags
        main_tag_ids = set(main_imported.raw_tags.values_list("id", flat=True))
        iof_tag_ids = set(iof_imported.raw_tags.values_list("id", flat=True))
        self.assertEqual(main_tag_ids, iof_tag_ids)
