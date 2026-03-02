import inspect
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from budget.models import Budget
from invoice import views
from invoice.models import Invoice
from invoice.utils import InvoiceValidationError, validate_invoice_data
from payment.models import Payment
from tag.models import Tag


class InvoiceViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="invoice-reg", email="invoice-reg@test.com", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None, *, id=None):
        payload = None if data is None else json.dumps(data)
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method("/", data=payload, content_type="application/json")

        target = inspect.unwrap(fn)
        if id is None:
            return target(request, user=self.user)
        return target(request, id=id, user=self.user)

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            status=kwargs.get("status", Invoice.STATUS_OPEN),
            type=kwargs.get("type", Invoice.Type.DEBIT),
            name=kwargs.get("name", "Inv"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            value_open=kwargs.get("value_open", Decimal("10.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
        )

    def _create_payment(self, invoice, **kwargs):
        return Payment.objects.create(
            status=kwargs.get("status", Payment.STATUS_OPEN),
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Pay"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", "r"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            invoice=invoice,
            user=self.user,
        )

    def test_parse_type_and_status_filter_helpers(self):
        self.assertEqual(views.parse_type("credit"), Invoice.Type.CREDIT)
        self.assertEqual(views.parse_type("debit"), Invoice.Type.DEBIT)
        with self.assertRaises(ValueError):
            views.parse_type("invalid")

        self.assertIsNone(views.get_status_filter("all"))
        self.assertEqual(views.get_status_filter("open"), Payment.STATUS_OPEN)
        self.assertEqual(views.get_status_filter("0"), Payment.STATUS_OPEN)
        self.assertEqual(views.get_status_filter("done"), Payment.STATUS_DONE)
        self.assertEqual(views.get_status_filter("1"), Payment.STATUS_DONE)
        self.assertIsNone(views.get_status_filter("x"))

    def test_get_all_invoice_view_with_filters(self):
        invoice_open = self._create_invoice(name="Open Inv", installments=2, fixed=True, value_open=Decimal("10.00"))
        invoice_done = self._create_invoice(name="Done Inv", installments=1, fixed=False, value_open=Decimal("0.00"))
        tag = Tag.objects.create(name="Tag", color="#111111", user=self.user)
        invoice_open.tags.add(tag)

        response = self._call(
            views.get_all_invoice_view,
            method="get",
            data={
                "status": "open",
                "type": str(Invoice.Type.DEBIT),
                "fixed": "true",
                "name__icontains": "Open",
                "installments": "2",
                "date__gte": "2026-01-01",
                "date__lte": "2026-01-31",
                "payment_date__gte": "2026-01-01",
                "payment_date__lte": "2026-01-31",
                "page": 1,
                "page_size": 10,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], invoice_open.id)

        done_response = self._call(
            views.get_all_invoice_view,
            method="get",
            data={"status": "done", "page": 1, "page_size": 10},
        )
        done_payload = json.loads(done_response.content)["data"]["data"]
        self.assertEqual(len(done_payload), 1)
        self.assertEqual(done_payload[0]["id"], invoice_done.id)

    def test_detail_invoice_view_success_and_not_found(self):
        invoice = self._create_invoice(name="Detail Inv")
        tag = Tag.objects.create(name="T", color="#222222", user=self.user)
        invoice.tags.add(tag)

        response = self._call(views.detail_invoice_view, id=invoice.id)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]
        self.assertEqual(data["id"], invoice.id)
        self.assertEqual(len(data["tags"]), 1)

        not_found = self._call(views.detail_invoice_view, id=99999)
        self.assertEqual(not_found.status_code, 404)

    def test_detail_invoice_payments_view_with_filters(self):
        invoice = self._create_invoice(name="Inv payments")
        self._create_payment(invoice, status=Payment.STATUS_OPEN, type=Payment.TYPE_DEBIT, name="Pay Open", fixed=True, active=True)
        self._create_payment(invoice, status=Payment.STATUS_DONE, type=Payment.TYPE_CREDIT, name="Pay Done", fixed=False, active=False)

        response = self._call(
            views.detail_invoice_payments_view,
            id=invoice.id,
            method="get",
            data={
                "status": "open",
                "type": str(Payment.TYPE_DEBIT),
                "name__icontains": "Open",
                "date__gte": "2026-01-01",
                "date__lte": "2026-01-31",
                "installments": "1",
                "payment_date__gte": "2026-01-01",
                "payment_date__lte": "2026-01-31",
                "fixed": "true",
                "active": "true",
                "page": 1,
                "page_size": 10,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Pay Open")

    def test_save_tag_invoice_view(self):
        invoice = self._create_invoice(name="Tag target")
        tag = Tag.objects.create(name="TagX", color="#fff", user=self.user)

        success = self._call(views.save_tag_invoice_view, method="post", id=invoice.id, data=[tag.id])
        self.assertEqual(success.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.tags.count(), 1)

        null_payload = self.rf.post("/", data="null", content_type="application/json")
        null_response = inspect.unwrap(views.save_tag_invoice_view)(null_payload, id=invoice.id, user=self.user)
        self.assertEqual(null_response.status_code, 404)

    def test_include_new_invoice_view_validations_and_success(self):
        missing = self._call(views.include_new_invoice_view, method="post", data={})
        self.assertEqual(missing.status_code, 400)

        invalid_type = self._call(
            views.include_new_invoice_view,
            method="post",
            data={
                "name": "New",
                "date": "2026-01-01",
                "installments": 1,
                "payment_date": "2026-01-02",
                "value": 10,
                "type": "invalid",
            },
        )
        self.assertEqual(invalid_type.status_code, 400)

        tag = Tag.objects.create(name="TG", color="#abc", user=self.user)
        with patch("invoice.views.generate_payments") as mocked_generate:
            success = self._call(
                views.include_new_invoice_view,
                method="post",
                data={
                    "name": "New",
                    "date": "2026-01-01",
                    "installments": 1,
                    "payment_date": "2026-01-02",
                    "value": 10,
                    "type": "debit",
                    "fixed": True,
                    "tags": [tag.id],
                },
            )
        self.assertEqual(success.status_code, 200)
        created = Invoice.objects.get(name="New")
        self.assertEqual(created.type, Invoice.Type.DEBIT)
        self.assertEqual(created.tags.count(), 1)
        mocked_generate.assert_called_once()

    def test_save_detail_view_success_and_not_found(self):
        invoice = self._create_invoice(name="Editable")
        tag = Tag.objects.create(name="T1", color="#999", user=self.user)

        success = self._call(
            views.save_detail_view,
            method="post",
            id=invoice.id,
            data={
                "name": "Updated",
                "date": "2026-02-01",
                "active": False,
                "tags": [tag.id],
            },
        )
        self.assertEqual(success.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.name, "Updated")
        self.assertFalse(invoice.active)
        self.assertEqual(invoice.tags.count(), 1)

        not_found = self._call(views.save_detail_view, method="post", id=99999, data={"name": "x"})
        self.assertEqual(not_found.status_code, 404)


class InvoiceUtilsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="invoice-utils", email="invoice-utils@test.com", password="123")

    def _build_invoice(self, **overrides):
        data = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Invoice",
            "date": date(2026, 1, 1),
            "installments": 1,
            "payment_date": date(2026, 1, 2),
            "fixed": False,
            "active": True,
            "value": Decimal("100.00"),
            "value_open": Decimal("100.00"),
            "value_closed": Decimal("0.00"),
            "user": self.user,
        }
        data.update(overrides)
        return Invoice(**data)

    def test_validate_invoice_data_accepts_valid_invoice(self):
        invoice = self._build_invoice()
        validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_installments_below_one(self):
        invoice = self._build_invoice(installments=0)
        with self.assertRaisesMessage(InvoiceValidationError, "parcelas"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_missing_user(self):
        invoice = self._build_invoice()
        invoice.user = None
        with self.assertRaisesMessage(InvoiceValidationError, "usu"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_missing_date(self):
        invoice = self._build_invoice(date=None)
        with self.assertRaisesMessage(InvoiceValidationError, "data"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_negative_total_value(self):
        invoice = self._build_invoice(value=Decimal("-1.00"), value_open=Decimal("-1.00"), value_closed=Decimal("0.00"))
        with self.assertRaisesMessage(InvoiceValidationError, "valor total"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_negative_open_value(self):
        invoice = self._build_invoice(value_open=Decimal("-1.00"), value_closed=Decimal("101.00"))
        with self.assertRaisesMessage(InvoiceValidationError, "aberto"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_negative_closed_value(self):
        invoice = self._build_invoice(value_open=Decimal("100.00"), value_closed=Decimal("-1.00"))
        with self.assertRaisesMessage(InvoiceValidationError, "fechado"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_open_value_above_total(self):
        invoice = self._build_invoice(value=Decimal("100.00"), value_open=Decimal("101.00"), value_closed=Decimal("0.00"))
        with self.assertRaisesMessage(InvoiceValidationError, "maior que o valor total"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_inconsistent_sum(self):
        invoice = self._build_invoice(value=Decimal("100.00"), value_open=Decimal("40.00"), value_closed=Decimal("50.00"))
        with self.assertRaisesMessage(InvoiceValidationError, "A soma"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_done_invoice_with_open_value(self):
        invoice = self._build_invoice(
            status=Invoice.STATUS_DONE,
            value=Decimal("100.00"),
            value_open=Decimal("10.00"),
            value_closed=Decimal("90.00"),
        )
        with self.assertRaisesMessage(InvoiceValidationError, "finalizada"):
            validate_invoice_data(invoice)

    def test_validate_invoice_data_rejects_open_invoice_with_zero_open_value(self):
        invoice = self._build_invoice(
            status=Invoice.STATUS_OPEN,
            value=Decimal("100.00"),
            value_open=Decimal("0.00"),
            value_closed=Decimal("100.00"),
        )
        with self.assertRaisesMessage(InvoiceValidationError, "em aberto"):
            validate_invoice_data(invoice)


class InvoiceModelsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="invoice-models", email="invoice-models@test.com", password="123")

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            status=kwargs.get("status", Invoice.STATUS_OPEN),
            type=kwargs.get("type", Invoice.Type.DEBIT),
            name=kwargs.get("name", "Model Inv"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("100.00")),
            value_open=kwargs.get("value_open", Decimal("100.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
        )

    def _create_payment(self, invoice, **kwargs):
        return Payment.objects.create(
            status=kwargs.get("status", Payment.STATUS_OPEN),
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Model Pay"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", "ref"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("50.00")),
            invoice=invoice,
            user=self.user,
        )

    def test_set_value_increases_total_and_open_value(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("100.00"))

        invoice.set_value(Decimal("25.00"))
        invoice.refresh_from_db()

        self.assertEqual(invoice.value, Decimal("125.00"))
        self.assertEqual(invoice.value_open, Decimal("125.00"))

    def test_get_next_open_payment_date_returns_earliest_active_open(self):
        invoice = self._create_invoice()
        self._create_payment(invoice, status=Payment.STATUS_DONE, payment_date=date(2026, 1, 3))
        self._create_payment(invoice, status=Payment.STATUS_OPEN, payment_date=date(2026, 1, 10))
        self._create_payment(invoice, status=Payment.STATUS_OPEN, payment_date=date(2026, 1, 5))
        self._create_payment(invoice, status=Payment.STATUS_OPEN, payment_date=date(2026, 1, 1), active=False)

        self.assertEqual(invoice.get_next_open_payment_date(), date(2026, 1, 5))

    def test_get_next_open_payment_date_returns_none_when_no_open_active_payment(self):
        invoice = self._create_invoice()
        self._create_payment(invoice, status=Payment.STATUS_DONE)
        self._create_payment(invoice, status=Payment.STATUS_OPEN, active=False)

        self.assertIsNone(invoice.get_next_open_payment_date())

    def test_close_value_marks_done_when_open_reaches_zero_and_updates_next_payment_date(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("100.00"), payment_date=date(2026, 1, 2))
        self._create_payment(invoice, status=Payment.STATUS_OPEN, payment_date=date(2026, 2, 1), value=Decimal("40.00"))

        invoice.close_value(Decimal("100.00"))
        invoice.refresh_from_db()

        self.assertEqual(invoice.value_open, Decimal("0.00"))
        self.assertEqual(invoice.value_closed, Decimal("100.00"))
        self.assertEqual(invoice.status, Invoice.STATUS_DONE)
        self.assertEqual(invoice.payment_date, date(2026, 2, 1))

    def test_update_value_recomputes_totals_from_active_payments(self):
        invoice = self._create_invoice(value=Decimal("0.00"), value_open=Decimal("0.00"), value_closed=Decimal("0.00"))
        self._create_payment(invoice, status=Payment.STATUS_OPEN, value=Decimal("30.00"), active=True)
        self._create_payment(invoice, status=Payment.STATUS_DONE, value=Decimal("70.00"), active=True)
        self._create_payment(invoice, status=Payment.STATUS_OPEN, value=Decimal("999.00"), active=False)

        invoice.update_value()
        invoice.refresh_from_db()

        self.assertEqual(invoice.value, Decimal("100.00"))
        self.assertEqual(invoice.value_open, Decimal("30.00"))
        self.assertEqual(invoice.value_closed, Decimal("70.00"))

    def test_validate_invoice_returns_value_mismatch(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("10.00"), value_closed=Decimal("80.00"))
        self.assertEqual(invoice.validate_invoice(), Invoice.ValidationStatus.VALUE_MISMATCH)

    def test_validate_invoice_returns_empty_payment_date(self):
        invoice = self._create_invoice(payment_date=None, value=Decimal("100.00"), value_open=Decimal("40.00"), value_closed=Decimal("60.00"))
        self.assertEqual(invoice.validate_invoice(), Invoice.ValidationStatus.EMPTY_PAYMENT_DATE)

    def test_validate_invoice_returns_budget_tag_not_found(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("40.00"), value_closed=Decimal("60.00"))
        self.assertEqual(invoice.validate_invoice(), Invoice.ValidationStatus.BUDGET_TAG_NOT_FOUND)

    def test_validate_invoice_returns_payments_not_found(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("40.00"), value_closed=Decimal("60.00"))
        tag = Tag.objects.create(name="Budgetless", color="#fff000", user=self.user)
        invoice.tags.add(tag)
        Budget.objects.create(tag=tag, allocation_percentage=Decimal("10.00"), user=self.user)

        self.assertEqual(invoice.validate_invoice(), Invoice.ValidationStatus.PAYMENTS_NOT_FOUND)

    def test_validate_invoice_returns_valid(self):
        invoice = self._create_invoice(value=Decimal("100.00"), value_open=Decimal("40.00"), value_closed=Decimal("60.00"))
        tag = Tag.objects.create(name="Budget tag", color="#00ff00", user=self.user)
        invoice.tags.add(tag)
        Budget.objects.create(tag=tag, allocation_percentage=Decimal("15.00"), user=self.user)
        self._create_payment(invoice, status=Payment.STATUS_OPEN, value=Decimal("40.00"), active=True)

        self.assertEqual(invoice.validate_invoice(), Invoice.ValidationStatus.VALID)
