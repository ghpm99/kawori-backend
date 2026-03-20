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


class CSVResolveImportsViewTestCase(TestCase):
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
        User.objects.create_user(
            username="normal", email="normal@normal.com", password="123"
        )

        # Criar tags para testes
        cls.tag1 = Tag.objects.create(name="Tag CSV 1", color="#FF0000", user=user)
        cls.tag2 = Tag.objects.create(name="Tag CSV 2", color="#00FF00", user=user)
        cls.budget_tag = Tag.objects.create(
            name="Budget CSV", color="#0000FF", user=user
        )

        # Criar invoice com tags para testes de merge
        cls.invoice_with_tags = Invoice.objects.create(
            name="Fatura com Tags",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("1000.00"),
            user=user,
        )
        cls.invoice_with_tags.tags.add(cls.tag1, cls.budget_tag)

        # Criar invoice sem tags
        cls.invoice_no_tags = Invoice.objects.create(
            name="Fatura sem Tags",
            date=datetime.now().date(),
            installments=1,
            payment_date=datetime.now().date() + timedelta(days=30),
            fixed=False,
            value=Decimal("500.00"),
            value_open=Decimal("500.00"),
            user=user,
        )

        # Criar pagamento existente para testes de merge
        cls.existing_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Pagamento Existente",
            description="Descrição do pagamento existente",
            date=datetime.now().date(),
            payment_date=datetime.now().date() + timedelta(days=5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("150.00"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice_with_tags,
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

    def test_csv_resolve_imports_view_success_transactions_new(self):
        """Testa sucesso da view com import_type transactions e estratégia new - deve criar ImportedPayment"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Nova 1",
                        "description": "Descrição nova 1",
                        "date": "2026-02-15",
                        "installments": 1,
                        "payment_date": "2026-02-20",
                        "value": "100.00",
                        "reference": "ref_nova_1",
                    },
                    "merge_group": "group1",
                },
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_CREDIT,
                        "name": "Transação Nova 2",
                        "description": "Descrição nova 2",
                        "date": "2026-02-16",
                        "installments": 1,
                        "payment_date": "2026-02-21",
                        "value": "200.00",
                        "reference": "ref_nova_2",
                    },
                    "merge_group": "group2",
                },
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        initial_count = ImportedPayment.objects.filter(user__username="test").count()

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn("data", data)
        self.assertEqual(len(data["data"]), 2)

        # Verificar se os ImportedPayments foram criados
        final_count = ImportedPayment.objects.filter(user__username="test").count()
        self.assertEqual(final_count, initial_count + 2)

        # Verificar estrutura dos dados retornados
        for item in data["data"]:
            expected_fields = [
                "import_payment_id",
                "reference",
                "action",
                "payment_id",
                "name",
                "value",
                "date",
                "payment_date",
                "tags",
                "has_budget_tag",
            ]
            for field in expected_fields:
                self.assertIn(field, item)

            # Verificar estratégia new
            self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_NEW)
            self.assertIsNone(item["payment_id"])
            self.assertFalse(item["has_budget_tag"])
            self.assertEqual(item["tags"], [])

    def test_csv_resolve_imports_view_success_card_payments_new(self):
        """Testa sucesso da view com import_type card_payments e estratégia new - deve criar ImportedPayment"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Cartão Nova 1",
                        "description": "Descrição cartão 1",
                        "date": "2026-02-15",
                        "installments": 1,
                        "payment_date": "2026-02-20",
                        "value": "150.00",
                        "reference": "cartao_nova_1",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Verificar se foi criado com import_source correto
        imported = ImportedPayment.objects.get(id=data["data"][0]["import_payment_id"])
        self.assertEqual(
            imported.import_source, ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS
        )

    def test_csv_resolve_imports_view_success_merge_strategy(self):
        """Testa sucesso da view com estratégia merge - deve criar ImportedPayment com tags do pagamento"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Merge",
                        "description": "Descrição merge",
                        "date": "2026-02-15",
                        "installments": 1,
                        "payment_date": "2026-02-20",
                        "value": "120.00",
                        "reference": "ref_merge",
                    },
                    "matched_payment_id": self.existing_payment.id,
                    "merge_group": "group_merge",
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        item = data["data"][0]

        # Verificar estratégia merge
        self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
        self.assertEqual(item["payment_id"], self.existing_payment.id)
        self.assertTrue(item["has_budget_tag"])  # Tem budget_tag no pagamento existente

        # Verificar se as tags foram copiadas
        self.assertEqual(len(item["tags"]), 2)  # tag1 e budget_tag

        tag_names = [tag["name"] for tag in item["tags"]]
        self.assertIn("Tag CSV 1", tag_names)
        self.assertIn("Budget CSV", tag_names)

        # Verificar se o ImportedPayment foi criado com as tags
        imported = ImportedPayment.objects.get(id=item["import_payment_id"])
        imported_tags = list(imported.raw_tags.all())
        self.assertEqual(len(imported_tags), 2)

    def test_csv_resolve_imports_view_success_multiple_merge_groups(self):
        """Testa sucesso da view com múltiplos merge groups - deve processar todos"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Group 1",
                        "reference": "ref_group_1",
                    },
                    "matched_payment_id": self.existing_payment.id,
                    "merge_group": "group1",
                },
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_CREDIT,
                        "name": "Transação Group 2",
                        "reference": "ref_group_2",
                    },
                    "matched_payment_id": self.existing_payment.id,
                    "merge_group": "group2",
                },
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Ambos devem ter estratégia merge
        for item in data["data"]:
            self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
            self.assertEqual(item["payment_id"], self.existing_payment.id)

    def test_csv_resolve_imports_view_success_update_existing_imported_payment(self):
        """Testa sucesso da view atualizando ImportedPayment existente editável"""
        # Criar ImportedPayment existente
        existing_imported = ImportedPayment.objects.create(
            user=User.objects.get(username="test"),
            reference="ref_existente",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Nome Antigo",
            raw_value=Decimal("100.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING,
        )

        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_CREDIT,
                        "name": "Nome Atualizado",
                        "reference": "ref_existente",  # Mesma referência
                        "value": "150.00",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Verificar se o ImportedPayment foi atualizado
        existing_imported.refresh_from_db()
        self.assertEqual(existing_imported.raw_type, Payment.TYPE_CREDIT)
        self.assertEqual(existing_imported.raw_name, "Nome Atualizado")
        self.assertEqual(existing_imported.raw_value, Decimal("150.00"))

    def test_csv_resolve_imports_view_skip_non_editable_imported_payment(self):
        """Testa view pulando ImportedPayment existente não editável"""
        # Criar ImportedPayment não editável
        non_editable_imported = ImportedPayment.objects.create(
            user=User.objects.get(username="test"),
            reference="ref_nao_editavel",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Não Editável",
            raw_value=Decimal("100.00"),
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,  # Não editável
        )

        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_CREDIT,
                        "name": "Tentativa Atualizar",
                        "reference": "ref_nao_editavel",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Não deve retornar nada porque pulou o não editável
        self.assertEqual(len(data["data"]), 0)

        # Verificar que o original não foi alterado
        non_editable_imported.refresh_from_db()
        self.assertEqual(non_editable_imported.raw_name, "Não Editável")

    def test_csv_resolve_imports_view_skip_without_mapped_payment(self):
        """Testa view pulando itens sem mapped_payment"""
        import_data = {
            "import": [
                {
                    "merge_group": "group1"
                    # Sem mapped_payment
                },
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Válida",
                        "reference": "ref_valida",
                    }
                },
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve processar apenas o item válido
        self.assertEqual(len(data["data"]), 1)

    def test_csv_resolve_imports_view_skip_invalid_matched_payment_id(self):
        """Testa view pulando itens com matched_payment_id inválido"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Inválida",
                        "reference": "ref_invalida",
                    },
                    "matched_payment_id": 99999,  # ID não existe
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve processar como new porque não encontrou o pagamento
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["action"], ImportedPayment.IMPORT_STRATEGY_NEW)

    def test_csv_resolve_imports_view_error_invalid_import_type(self):
        """Testa erro da view com import_type inválido - deve retornar erro 400"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação",
                        "reference": "ref_test",
                    }
                }
            ],
            "import_type": "tipo_invalido",
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)

        self.assertIn("msg", data)
        self.assertEqual(data["msg"], "Tipo de importação invalido")

    def test_csv_resolve_imports_view_error_empty_import_list(self):
        """Testa view com lista de importação vazia - deve retornar lista vazia"""
        import_data = {
            "import": [],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 0)

    def test_csv_resolve_imports_view_error_missing_import_field(self):
        """Testa view sem campo import - deve retornar lista vazia"""
        import_data = {
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
            # Sem campo "import"
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 0)

    def test_csv_resolve_imports_view_error_invalid_json(self):
        """Testa erro da view com JSON inválido - deve retornar erro 400"""
        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data="json_invalido",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_resolve_imports_view_error_wrong_method_get(self):
        """Testa erro da view com método GET - deve retornar erro 405"""
        response = self.client.get(reverse("financial_csv_resolve_imports_view"))

        self.assertEqual(response.status_code, 405)

    def test_csv_resolve_imports_view_unauthorized_user(self):
        """Testa acesso negado para usuário sem permissão financial"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Não Autorizada",
                        "reference": "ref_nao_autorizada",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        # Usar cookies do usuário normal
        for key, morsel in self.cookies_normal.items():
            self.client.cookies[key] = morsel.value

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_csv_resolve_imports_view_no_authentication(self):
        """Testa acesso sem autenticação"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Sem Auth",
                        "reference": "ref_sem_auth",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        # Limpar cookies
        self.client.cookies.clear()

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        # Deve retornar erro 401 ou 403
        self.assertIn(response.status_code, [401, 403])

    def test_csv_resolve_imports_view_edge_case_default_import_type(self):
        """Testa edge case sem import_type - deve usar padrão transactions"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Padrão",
                        "reference": "ref_padrao",
                    }
                }
            ]
            # Sem import_type
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Verificar se usou o padrão transactions
        imported = ImportedPayment.objects.get(id=data["data"][0]["import_payment_id"])
        self.assertEqual(
            imported.import_source, ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
        )

    def test_csv_resolve_imports_view_edge_case_merge_without_tags(self):
        """Testa edge case merge com pagamento sem tags - deve funcionar sem tags"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Merge Sem Tags",
                        "reference": "ref_merge_sem_tags",
                    },
                    "matched_payment_id": (
                        self.invoice_no_tags.payments.first().id
                        if self.invoice_no_tags.payments.exists()
                        else None
                    ),
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        # Criar pagamento na invoice sem tags se não existir
        if not self.invoice_no_tags.payments.exists():
            payment_no_tags = Payment.objects.create(
                type=Payment.TYPE_DEBIT,
                name="Pagamento Sem Tags",
                date=datetime.now().date(),
                payment_date=datetime.now().date() + timedelta(days=5),
                installments=1,
                fixed=False,
                active=True,
                value=Decimal("100.00"),
                status=Payment.STATUS_OPEN,
                user=User.objects.get(username="test"),
                invoice=self.invoice_no_tags,
            )
            import_data["import"][0]["matched_payment_id"] = payment_no_tags.id

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        item = data["data"][0]
        self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
        self.assertFalse(item["has_budget_tag"])
        self.assertEqual(item["tags"], [])

    def test_csv_resolve_imports_view_edge_case_very_large_import_list(self):
        """Testa edge case com lista de importação muito grande - deve processar todos"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": f"Transação Grande {i}",
                        "reference": f"ref_grande_{i}",
                        "value": "100.00",
                    }
                }
                for i in range(50)  # 50 itens
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 50)

        # Verificar se todos foram criados
        for item in data["data"]:
            self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_NEW)

    def test_csv_resolve_imports_view_edge_case_duplicate_references_same_user(self):
        """Testa edge case com referências duplicadas para mesmo usuário - deve atualizar existente"""
        # Criar ImportedPayment inicial
        initial_imported = ImportedPayment.objects.create(
            user=User.objects.get(username="test"),
            reference="ref_duplicada",
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Nome Inicial",
            raw_value=Decimal("100.00"),
            status=ImportedPayment.IMPORT_STATUS_PENDING,
        )

        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_CREDIT,
                        "name": "Nome Atualizado",
                        "reference": "ref_duplicada",  # Mesma referência
                        "value": "150.00",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)

        # Verificar se atualizou o existente
        initial_imported.refresh_from_db()
        self.assertEqual(initial_imported.raw_type, Payment.TYPE_CREDIT)
        self.assertEqual(initial_imported.raw_name, "Nome Atualizado")
        self.assertEqual(initial_imported.raw_value, Decimal("150.00"))

    def test_csv_resolve_imports_view_response_structure(self):
        """Testa estrutura da resposta da view"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação Estrutura",
                        "reference": "ref_estrutura",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Verificar estrutura principal
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        # Verificar estrutura de cada item
        if data["data"]:
            item = data["data"][0]
            expected_fields = [
                "import_payment_id",
                "reference",
                "action",
                "payment_id",
                "name",
                "value",
                "date",
                "payment_date",
                "tags",
                "has_budget_tag",
            ]
            for field in expected_fields:
                self.assertIn(field, item)

            # Verificar tipos
            self.assertIsInstance(item["import_payment_id"], int)
            self.assertIsInstance(item["reference"], str)
            self.assertIsInstance(item["action"], str)
            self.assertIsInstance(item["name"], str)
            self.assertIsInstance(item["value"], float)
            self.assertIsInstance(item["tags"], list)
            self.assertIsInstance(item["has_budget_tag"], bool)

    def test_csv_resolve_imports_view_completed_reimport_returns_previous_data(self):
        """Testa que reimportar reference COMPLETED retorna dados anteriores em vez de skipar"""
        user = User.objects.get(username="test")

        Budget.objects.get_or_create(
            user=user,
            tag=self.budget_tag,
            defaults={"allocation_percentage": Decimal("10.00")},
        )

        # Criar ImportedPayment já completado com tags e merge_group
        completed_imported = ImportedPayment.objects.create(
            user=user,
            reference="ref_completed",
            import_source=ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_MERGE,
            merge_group="completed_group",
            matched_payment=self.existing_payment,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Discord",
            raw_value=Decimal("30.00"),
            raw_date="2026-02-15",
            raw_payment_date="2026-02-20",
            status=ImportedPayment.IMPORT_STATUS_COMPLETED,
        )
        completed_imported.raw_tags.set([self.tag1, self.budget_tag])

        # Reimportar com a mesma reference
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Discord",
                        "reference": "ref_completed",
                        "value": "30.00",
                        "date": "2026-02-15",
                        "payment_date": "2026-02-20",
                    }
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Deve retornar dados do import anterior (não skipar silenciosamente)
        self.assertEqual(len(data["data"]), 1)

        item = data["data"][0]
        self.assertEqual(item["import_payment_id"], completed_imported.id)
        self.assertEqual(item["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
        self.assertEqual(item["payment_id"], self.existing_payment.id)
        self.assertEqual(item["merge_group"], "completed_group")
        self.assertTrue(item["completed"])
        self.assertTrue(item["has_budget_tag"])

        # Tags devem vir populadas
        tag_names = {t["name"] for t in item["tags"]}
        self.assertIn("Tag CSV 1", tag_names)
        self.assertIn("Budget CSV", tag_names)

    def test_csv_resolve_imports_view_merge_group_tag_propagation(self):
        """Testa que tags são propagadas do item principal para itens do mesmo merge_group"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Discord",
                        "reference": "ref_discord_prop",
                        "value": "30.00",
                        "date": "2026-02-15",
                        "payment_date": "2026-02-20",
                    },
                    "matched_payment_id": self.existing_payment.id,
                    "merge_group": "discord_mg",
                },
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "IOF Discord",
                        "reference": "ref_iof_discord_prop",
                        "value": "2.00",
                        "date": "2026-02-15",
                        "payment_date": "2026-02-20",
                    },
                    "merge_group": "discord_mg",  # Mesmo grupo, sem matched_payment_id
                },
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_CARD_PAYMENTS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 2)

        # Discord (principal com merge) deve ter tags
        discord_item = next(i for i in data["data"] if i["name"] == "Discord")
        self.assertEqual(discord_item["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
        self.assertTrue(len(discord_item["tags"]) > 0)

        # IOF Discord deve ter herdado as tags via merge_group
        iof_item = next(i for i in data["data"] if i["name"] == "IOF Discord")
        self.assertEqual(len(iof_item["tags"]), len(discord_item["tags"]))
        self.assertEqual(iof_item["has_budget_tag"], discord_item["has_budget_tag"])

        # Verificar no banco
        iof_imported = ImportedPayment.objects.get(id=iof_item["import_payment_id"])
        iof_tags = set(iof_imported.raw_tags.values_list("id", flat=True))
        discord_imported = ImportedPayment.objects.get(
            id=discord_item["import_payment_id"]
        )
        discord_tags = set(discord_imported.raw_tags.values_list("id", flat=True))
        self.assertEqual(iof_tags, discord_tags)

    def test_csv_resolve_imports_view_response_includes_merge_group(self):
        """Testa que a resposta inclui o campo merge_group"""
        import_data = {
            "import": [
                {
                    "mapped_payment": {
                        "type": Payment.TYPE_DEBIT,
                        "name": "Transação MG",
                        "reference": "ref_mg_test",
                    },
                    "merge_group": "test_mg",
                }
            ],
            "import_type": ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
        }

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(import_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(len(data["data"]), 1)
        self.assertIn("merge_group", data["data"][0])
        self.assertEqual(data["data"][0]["merge_group"], "test_mg")
