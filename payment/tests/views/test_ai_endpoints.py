import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from budget.models import Budget
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class PaymentAIEndpointsViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        user = User.objects.create_superuser(
            username="test", email="test@test.com", password="123"
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)

        cls.user = user

        cls.tag_health = Tag.objects.create(name="Saude", color="#FF0000", user=user)
        cls.tag_transport = Tag.objects.create(
            name="Transporte", color="#00AAFF", user=user
        )
        Budget.objects.create(
            user=user, tag=cls.tag_health, allocation_percentage=Decimal("25.00")
        )

        cls.invoice = Invoice.objects.create(
            name="Fatura Teste",
            date=date(2026, 3, 1),
            installments=1,
            payment_date=date(2026, 3, 10),
            fixed=False,
            value=Decimal("500.00"),
            value_open=Decimal("100.00"),
            value_closed=Decimal("400.00"),
            user=user,
        )
        cls.invoice.tags.add(cls.tag_health)

        cls.reference_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="UBER*TRIP",
            description="Corrida",
            date=date(2026, 3, 9),
            payment_date=date(2026, 3, 10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("58.90"),
            status=Payment.STATUS_OPEN,
            user=user,
            invoice=cls.invoice,
            reference="",
        )

        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Farmacia Sao Joao",
            description="Medicamentos",
            date=date(2026, 2, 20),
            payment_date=date(2026, 2, 20),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("120.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice,
            reference="",
        )

        for day in range(1, 6):
            Payment.objects.create(
                type=Payment.TYPE_DEBIT,
                name=f"Despesa comum {day}",
                description="Historico comum",
                date=date(2026, 2, day),
                payment_date=date(2026, 2, day),
                installments=1,
                fixed=False,
                active=True,
                value=Decimal("45.00"),
                status=Payment.STATUS_DONE,
                user=user,
                invoice=cls.invoice,
                reference="",
            )

        cls.anomalous_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="PIX Emergencial",
            description="Transferencia fora do padrao",
            date=date(2026, 3, 12),
            payment_date=date(2026, 3, 12),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("980.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=cls.invoice,
            reference="",
        )

        token_response = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )
        cls.cookies = token_response.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_csv_ai_map_returns_suggestions(self):
        response = self.client.post(
            reverse("financial_csv_ai_map"),
            data=json.dumps(
                {
                    "file_name": "nubank_marco.csv",
                    "headers": ["Dt Pgto", "Historico", "Vl.", "Parc."],
                    "sample_rows": [
                        {
                            "Dt Pgto": "14/03/2026",
                            "Historico": "UBER*TRIP",
                            "Vl.": "32,40",
                            "Parc.": "1/1",
                        }
                    ],
                    "import_type": "card_payments",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        suggestions = {
            item["csv_column"]: item["system_field"] for item in payload["suggestions"]
        }
        self.assertEqual(suggestions.get("Dt Pgto"), "payment_date")
        self.assertEqual(suggestions.get("Vl."), "value")
        self.assertEqual(suggestions.get("Parc."), "installments")

    def test_csv_ai_map_returns_error_on_invalid_json(self):
        response = self.client.post(
            reverse("financial_csv_ai_map"),
            data="invalid_json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "JSON inválido")

    def test_csv_ai_map_returns_error_without_headers(self):
        response = self.client.post(
            reverse("financial_csv_ai_map"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "headers is required")

    def test_csv_ai_normalize_returns_corrections(self):
        response = self.client.post(
            reverse("financial_csv_ai_normalize"),
            data=json.dumps(
                {
                    "transactions": [
                        {
                            "id": "tx-1",
                            "mapped_data": {
                                "name": "  Farmacia Sao Joao  ",
                                "description": "  Compra  ",
                                "date": "14-03-26",
                                "payment_date": "14-03-26",
                                "value": "R$ 1.234,56",
                                "installments": "1/1",
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertGreaterEqual(payload["total_corrections"], 3)
        normalized = payload["normalized_transactions"][0]["mapped_data"]
        self.assertEqual(normalized["date"], "2026-03-14")
        self.assertEqual(normalized["payment_date"], "2026-03-14")
        self.assertEqual(normalized["value"], 1234.56)

    def test_csv_ai_normalize_returns_error_on_invalid_json(self):
        response = self.client.post(
            reverse("financial_csv_ai_normalize"),
            data="invalid_json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "JSON inválido")

    def test_csv_ai_normalize_returns_error_without_transactions(self):
        response = self.client.post(
            reverse("financial_csv_ai_normalize"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "transactions is required")

    def test_csv_ai_reconcile_returns_best_match(self):
        response = self.client.post(
            reverse("financial_csv_ai_reconcile"),
            data=json.dumps(
                {
                    "transactions": [
                        {
                            "id": "tx-1",
                            "mapped_data": {
                                "name": "UBER TRIP",
                                "description": "Corrida",
                                "date": "2026-03-10",
                                "payment_date": "2026-03-10",
                                "value": "58.90",
                                "installments": 1,
                                "reference": "",
                                "type": Payment.TYPE_DEBIT,
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertEqual(len(payload["matches"]), 1)
        best_match = payload["matches"][0]["best_match"]
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match["payment_id"], self.reference_payment.id)

    def test_csv_ai_reconcile_returns_error_on_invalid_json(self):
        response = self.client.post(
            reverse("financial_csv_ai_reconcile"),
            data="invalid_json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "JSON inválido")

    def test_csv_ai_reconcile_returns_error_without_transactions(self):
        response = self.client.post(
            reverse("financial_csv_ai_reconcile"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "transactions is required")

    def test_ai_tag_suggestions_returns_recommendation(self):
        response = self.client.post(
            reverse("financial_ai_tag_suggestions"),
            data=json.dumps(
                {
                    "transactions": [
                        {
                            "id": "tx-tag",
                            "mapped_data": {
                                "name": "Farmacia Sao Joao",
                                "description": "Compra de medicamento",
                                "value": "89.90",
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertEqual(len(payload["suggestions"]), 1)
        item = payload["suggestions"][0]
        self.assertIn("recommended_tag_id", item)
        self.assertGreaterEqual(len(item["tag_suggestions"]), 1)

    def test_ai_tag_suggestions_returns_error_on_invalid_json(self):
        response = self.client.post(
            reverse("financial_ai_tag_suggestions"),
            data="invalid_json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "JSON inválido")

    def test_ai_tag_suggestions_returns_error_without_transactions(self):
        response = self.client.post(
            reverse("financial_ai_tag_suggestions"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "transactions is required")

    def test_statement_anomalies_returns_detected_items(self):
        response = self.client.get(
            reverse("financial_statement_anomalies"),
            data={"date_from": "2026-03-01", "date_to": "2026-03-31"},
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]

        self.assertGreaterEqual(payload["total_anomalies"], 1)
        anomaly_ids = [item["payment_id"] for item in payload["anomalies"]]
        self.assertIn(self.anomalous_payment.id, anomaly_ids)

    def test_statement_anomalies_returns_error_when_dates_are_missing(self):
        response = self.client.get(reverse("financial_statement_anomalies"))

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["msg"], "date_from and date_to are required")

    def test_statement_anomalies_returns_error_on_invalid_date_format(self):
        response = self.client.get(
            reverse("financial_statement_anomalies"),
            data={"date_from": "01-03-2026", "date_to": "31-03-2026"},
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(
            payload["msg"], "date_from and date_to must be in YYYY-MM-DD format"
        )

    def test_statement_anomalies_returns_error_when_date_from_gt_date_to(self):
        response = self.client.get(
            reverse("financial_statement_anomalies"),
            data={"date_from": "2026-03-31", "date_to": "2026-03-01"},
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(
            payload["msg"], "date_from must be less than or equal to date_to"
        )
