import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from budget.models import Budget
from invoice.models import Invoice
from payment.models import ImportedPayment, Payment
from tag.models import Tag
from payment.views import get_status_filter


class PaymentViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        cls.user = User.objects.create_superuser(username="regression", email="regression@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(cls.user)

        token = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "regression", "password": "123"},
        )
        cls.cookies = token.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            name=kwargs.get("name", "Invoice"),
            date=kwargs.get("date", date.today()),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date.today() + timedelta(days=5)),
            fixed=kwargs.get("fixed", False),
            value=kwargs.get("value", Decimal("1000.00")),
            value_open=kwargs.get("value_open", Decimal("1000.00")),
            user=self.user,
            active=kwargs.get("active", True),
        )

    def _create_imported_payment(self, reference="import-ref", status=ImportedPayment.IMPORT_STATUS_PENDING):
        return ImportedPayment.objects.create(
            user=self.user,
            reference=reference,
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="Imported",
            raw_description="",
            raw_date=date.today(),
            raw_installments=1,
            raw_payment_date=date.today(),
            raw_value=Decimal("10.00"),
            status=status,
        )

    def test_save_new_view_accepts_string_value(self):
        response = self.client.post(
            reverse("financial_save_new"),
            data=json.dumps(
                {
                    "type": Payment.TYPE_DEBIT,
                    "name": "String value",
                    "date": "2026-02-01",
                    "payment_date": "2026-02-10",
                    "installments": 2,
                    "fixed": False,
                    "value": "100.00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.filter(user=self.user, name="String value").count(), 2)

    def test_save_detail_view_updates_type_zero_and_string_value(self):
        invoice = self._create_invoice(value_open=Decimal("200.00"))
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Edit payment",
            date=date.today(),
            payment_date=date.today() + timedelta(days=1),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("50.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": payment.id}),
            data=json.dumps({"type": Payment.TYPE_CREDIT, "value": "80.00"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.type, Payment.TYPE_CREDIT)
        self.assertEqual(payment.value, Decimal("80.00"))
        self.assertEqual(invoice.value_open, Decimal("230.00"))

    def test_get_payments_month_aggregates_by_month(self):
        invoice = self._create_invoice(name="Monthly aggregate")
        today = date.today().replace(day=1)
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="P1",
            date=today,
            payment_date=today + timedelta(days=1),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )
        Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="P2",
            date=today,
            payment_date=today + timedelta(days=2),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("20.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(reverse("financial_get_payments_month"))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertEqual(len(payload["data"]), 1)
        aggregated = payload["data"][0]
        self.assertEqual(aggregated["date"], today.isoformat())
        self.assertEqual(aggregated["total_payments"], 2)
        self.assertEqual(aggregated["total_value_debit"], 10.0)
        self.assertEqual(aggregated["total_value_credit"], 20.0)
        self.assertEqual(aggregated["total"], 30.0)
        self.assertIn("dateTimestamp", aggregated)

    def test_csv_resolve_imports_view_handles_invalid_match_and_missing_optional_fields(self):
        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(
                {
                    "import": [
                        {
                            "mapped_payment": {
                                "type": Payment.TYPE_DEBIT,
                                "name": "CSV minimal",
                                "reference": "csv-minimal",
                            },
                            "matched_payment_id": 999999,
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["action"], ImportedPayment.IMPORT_STRATEGY_NEW)
        self.assertIsNone(payload["data"][0]["payment_id"])

        imported = ImportedPayment.objects.get(reference="csv-minimal", user=self.user)
        self.assertEqual(imported.raw_installments, 1)
        self.assertEqual(imported.raw_description, "")

    def test_csv_resolve_imports_view_rejects_invalid_import_type(self):
        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps({"import": [], "import_type": "invalid-type"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_csv_import_view_queues_only_items_with_budget_tags(self):
        regular_tag = Tag.objects.create(name="Regular", color="#111111", user=self.user)
        budget_tag = Tag.objects.create(name="Budget", color="#222222", user=self.user)
        Budget.objects.create(user=self.user, tag=budget_tag, allocation_percentage=Decimal("20.00"))

        queued_target = self._create_imported_payment(reference="queue-me")
        skip_target = self._create_imported_payment(reference="skip-me")

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps(
                {
                    "data": [
                        {"import_payment_id": queued_target.id, "tags": [regular_tag.id, budget_tag.id]},
                        {"import_payment_id": skip_target.id, "tags": [regular_tag.id]},
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["total"], 1)

        queued_target.refresh_from_db()
        skip_target.refresh_from_db()
        self.assertEqual(queued_target.status, ImportedPayment.IMPORT_STATUS_QUEUED)
        self.assertEqual(skip_target.status, ImportedPayment.IMPORT_STATUS_PENDING)

    def test_get_csv_mapping_validates_headers(self):
        missing_response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(missing_response.status_code, 400)

        ok_response = self.client.post(
            reverse("financial_get_csv_mapping"),
            data=json.dumps({"headers": ["descrição", "valor"]}),
            content_type="application/json",
        )
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(len(json.loads(ok_response.content)["data"]), 2)

    def test_process_csv_upload_maps_rows(self):
        class DummyProcessed:
            def __init__(self, value):
                self.value = value

            def to_dict(self):
                return {"value": self.value}

        with patch("payment.views.process_csv_row", side_effect=[DummyProcessed(1), DummyProcessed(2)]) as mocked:
            response = self.client.post(
                reverse("financial_process_csv_upload"),
                data=json.dumps(
                    {
                        "headers": [{"csv_column": "x", "system_field": "y"}],
                        "body": [{"x": "a"}, {"x": "b"}],
                        "import_type": "transactions",
                        "payment_date": "2026-02-01",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["data"], [{"value": 1}, {"value": 2}])
        self.assertEqual(mocked.call_count, 2)

    def test_get_all_scheduled_view_returns_paginated_payload(self):
        invoice = self._create_invoice(name="Schedule invoice")
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Scheduled 1",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("1.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )
        Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Scheduled 2",
            date=date.today(),
            payment_date=date.today() + timedelta(days=1),
            installments=1,
            fixed=True,
            active=False,
            value=Decimal("2.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(reverse("financial_get_all_scheduled"), {"page_size": 1})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(payload["current_page"], 1)
        self.assertEqual(payload["total_pages"], 2)
        self.assertEqual(len(payload["data"]), 1)

    def test_get_all_view_returns_invoice_and_tags(self):
        invoice = self._create_invoice(name="Invoice list")
        tag = Tag.objects.create(name="X", color="#123456", user=self.user)
        invoice.tags.add(tag)
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="List payment",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("9.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(
            reverse("financial_get_all"),
            {
                "status": "open",
                "type": Payment.TYPE_DEBIT,
                "name__icontains": "List",
                "date__gte": "2020-01-01",
                "date__lte": "2030-01-01",
                "installments": "1",
                "payment_date__gte": "2020-01-01",
                "payment_date__lte": "2030-01-01",
                "fixed": "false",
                "active": "true",
                "invoice_id": invoice.id,
                "invoice": "Invoice",
                "page": 1,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["id"], payment.id)
        self.assertEqual(payload["data"][0]["invoice_name"], "Invoice list")
        self.assertEqual(len(payload["data"][0]["tags"]), 1)

    def test_detail_view_returns_404_for_missing_payment(self):
        response = self.client.get(reverse("financial_detail_view", kwargs={"id": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_detail_view_returns_payment_data(self):
        invoice = self._create_invoice(name="Detail invoice")
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Detail payment",
            date=date.today(),
            payment_date=date.today(),
            installments=3,
            fixed=True,
            active=True,
            value=Decimal("15.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment.id}))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(payload["id"], payment.id)
        self.assertEqual(payload["name"], "Detail payment")
        self.assertEqual(payload["invoice_name"], "Detail invoice")

    def test_detail_view_inactive_payment_returns_404(self):
        invoice = self._create_invoice(name="Detail invoice inactive")
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Inactive payment",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=False,
            value=Decimal("15.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(reverse("financial_detail_view", kwargs={"id": payment.id}))
        self.assertEqual(response.status_code, 404)

    def test_save_detail_view_handles_not_found_and_done_payment(self):
        not_found_response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": 99999}),
            data=json.dumps({"name": "x"}),
            content_type="application/json",
        )
        self.assertEqual(not_found_response.status_code, 404)

        invoice = self._create_invoice(name="Done invoice")
        done_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Done payment",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("20.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )
        done_response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": done_payment.id}),
            data=json.dumps({"name": "new"}),
            content_type="application/json",
        )
        self.assertEqual(done_response.status_code, 500)

    def test_save_detail_view_updates_name_date_flags(self):
        invoice = self._create_invoice(name="Edit flags")
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Original",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("5.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.post(
            reverse("financial_save_detail_view", kwargs={"id": payment.id}),
            data=json.dumps({"name": "Updated", "payment_date": "2027-01-01", "fixed": True, "active": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.name, "Updated")
        self.assertEqual(str(payment.payment_date), "2027-01-01")
        self.assertTrue(payment.fixed)
        self.assertFalse(payment.active)

    def test_payoff_detail_view_fixed_invoice_creates_new_invoice(self):
        original_invoice = self._create_invoice(name="Fixed invoice", fixed=True, payment_date=date.today())
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Payoff me",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=True,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=original_invoice,
        )
        before_count = Invoice.objects.filter(user=self.user, name="Fixed invoice").count()

        with patch("payment.views.generate_payments") as mocked_generate:
            response = self.client.post(reverse("financial_payoff_detail_view", kwargs={"id": payment.id}))

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_DONE)
        self.assertEqual(Invoice.objects.filter(user=self.user, name="Fixed invoice").count(), before_count + 1)
        mocked_generate.assert_called_once()

    def test_payoff_detail_view_handles_not_found_and_already_done(self):
        not_found = self.client.post(reverse("financial_payoff_detail_view", kwargs={"id": 99999}))
        self.assertEqual(not_found.status_code, 400)

        invoice = self._create_invoice(name="Done payoff")
        done_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Done",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )
        done_response = self.client.post(reverse("financial_payoff_detail_view", kwargs={"id": done_payment.id}))
        self.assertEqual(done_response.status_code, 400)

    def test_get_all_scheduled_view_applies_all_filters(self):
        invoice = self._create_invoice(name="Sched all")
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Filter all",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("7.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )
        response = self.client.get(
            reverse("financial_get_all_scheduled"),
            {
                "status": "open",
                "type": Payment.TYPE_DEBIT,
                "name__icontains": "Filter",
                "date__gte": "2020-01-01",
                "date__lte": "2030-01-01",
                "installments": "1",
                "payment_date__gte": "2020-01-01",
                "payment_date__lte": "2030-01-01",
                "fixed": "false",
                "active": "true",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)["data"]["data"]), 1)

    def test_csv_resolve_imports_view_skips_missing_mapped_payment_and_non_editable_existing(self):
        non_editable = self._create_imported_payment(
            reference="non-editable",
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,
        )
        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(
                {
                    "import": [
                        {"merge_group": "g1"},
                        {
                            "mapped_payment": {
                                "type": Payment.TYPE_DEBIT,
                                "name": "Should skip",
                                "reference": non_editable.reference,
                            }
                        },
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], [])

    def test_csv_import_view_skips_non_editable(self):
        budget_tag = Tag.objects.create(name="B2", color="#abcdef", user=self.user)
        Budget.objects.create(user=self.user, tag=budget_tag, allocation_percentage=Decimal("10.00"))
        non_editable = self._create_imported_payment(
            reference="queue-skip",
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,
        )

        response = self.client.post(
            reverse("financial_csv_import_view"),
            data=json.dumps({"data": [{"import_payment_id": non_editable.id, "tags": [budget_tag.id]}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["total"], 0)

    def test_csv_resolve_imports_view_merge_keeps_matched_payment_id(self):
        invoice = self._create_invoice(name="Merge invoice")
        matched = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Matched",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("11.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.post(
            reverse("financial_csv_resolve_imports_view"),
            data=json.dumps(
                {
                    "import": [
                        {
                            "mapped_payment": {
                                "type": Payment.TYPE_DEBIT,
                                "name": "CSV merge",
                                "reference": "csv-merge",
                                "date": "2026-01-01",
                                "payment_date": "2026-01-01",
                                "installments": 1,
                                "value": "10.00",
                            },
                            "matched_payment_id": matched.id,
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(payload[0]["action"], ImportedPayment.IMPORT_STRATEGY_MERGE)
        self.assertEqual(payload[0]["payment_id"], matched.id)

    def test_get_status_filter_handles_supported_values(self):
        self.assertIsNone(get_status_filter("all"))
        self.assertEqual(get_status_filter("open"), Payment.STATUS_OPEN)
        self.assertEqual(get_status_filter("0"), Payment.STATUS_OPEN)
        self.assertEqual(get_status_filter("done"), Payment.STATUS_DONE)
        self.assertEqual(get_status_filter("1"), Payment.STATUS_DONE)
        self.assertIsNone(get_status_filter("invalid"))
