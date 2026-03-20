from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from invoice.models import Invoice
from payment.models import ImportedPayment, Payment


class PaymentModelsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="models-user", password="123")

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            name=kwargs.get("name", "Invoice M"),
            date=kwargs.get("date", date.today()),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date.today()),
            fixed=kwargs.get("fixed", False),
            value=kwargs.get("value", Decimal("100.00")),
            value_open=kwargs.get("value_open", Decimal("100.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
        )

    def _create_payment(self, **kwargs):
        return Payment.objects.create(
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Payment M"),
            description=kwargs.get("description", "desc"),
            reference=kwargs.get("reference", "ref"),
            date=kwargs.get("date", date.today()),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date.today()),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            status=kwargs.get("status", Payment.STATUS_OPEN),
            invoice=kwargs.get("invoice", self._create_invoice()),
            user=self.user,
        )

    def test_set_value_updates_payment_and_invoice(self):
        invoice = self._create_invoice(
            value=Decimal("100.00"), value_open=Decimal("100.00")
        )
        payment = self._create_payment(invoice=invoice, value=Decimal("10.00"))

        payment.set_value(Decimal("30.00"))
        payment.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(payment.value, Decimal("30.00"))
        self.assertEqual(invoice.value, Decimal("130.00"))
        self.assertEqual(invoice.value_open, Decimal("130.00"))

    def test_close_value_updates_status_and_invoice(self):
        invoice = self._create_invoice(value_open=Decimal("10.00"))
        payment = self._create_payment(
            invoice=invoice, value=Decimal("10.00"), status=Payment.STATUS_OPEN
        )

        payment.close_value()
        payment.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_DONE)
        self.assertEqual(invoice.status, Invoice.STATUS_DONE)
        self.assertEqual(invoice.value_open, Decimal("0.00"))
        self.assertEqual(invoice.value_closed, Decimal("10.00"))

    def test_to_dict_without_related(self):
        payment = self._create_payment(value=Decimal("12.50"))
        data = payment.to_dict()

        self.assertEqual(data["id"], payment.id)
        self.assertEqual(data["type"], payment.type)
        self.assertEqual(data["name"], payment.name)
        self.assertEqual(data["date"], payment.date.isoformat())
        self.assertEqual(data["payment_date"], payment.payment_date.isoformat())
        self.assertEqual(data["value"], 12.5)
        self.assertEqual(data["invoice_id"], payment.invoice_id)
        self.assertEqual(data["user_id"], payment.user_id)
        self.assertNotIn("invoice", data)
        self.assertNotIn("user", data)

    def test_to_dict_with_related_fallback_when_related_missing(self):
        payment = Payment(
            id=999,
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Detached",
            description="",
            reference="",
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            active=True,
            value=Decimal("1.00"),
            invoice_id=777777,
            user_id=888888,
        )
        data = payment.to_dict(include_related=True)

        self.assertEqual(data["invoice"], {"id": 777777})
        self.assertEqual(data["user"], {"id": 888888})

    def test_to_dict_handles_none_dates_and_value(self):
        payment = Payment(
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="None values",
            description="",
            reference="",
            installments=1,
            fixed=False,
            active=True,
            user=self.user,
        )
        payment.date = None
        payment.payment_date = None
        payment.value = None

        data = payment.to_dict()
        self.assertIsNone(data["date"])
        self.assertIsNone(data["payment_date"])
        self.assertIsNone(data["value"])


class ImportedPaymentModelsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="imported-user", password="123")

    def _create_imported(self, **kwargs):
        return ImportedPayment.objects.create(
            import_source=kwargs.get(
                "import_source", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
            ),
            import_strategy=kwargs.get(
                "import_strategy", ImportedPayment.IMPORT_STRATEGY_NEW
            ),
            reference=kwargs.get("reference", "r1"),
            status=kwargs.get("status", ImportedPayment.IMPORT_STATUS_PENDING),
            raw_type=kwargs.get("raw_type", Payment.TYPE_DEBIT),
            raw_name=kwargs.get("raw_name", "name"),
            raw_description=kwargs.get("raw_description", ""),
            raw_date=kwargs.get("raw_date", date.today()),
            raw_installments=kwargs.get("raw_installments", 1),
            raw_payment_date=kwargs.get("raw_payment_date", date.today()),
            raw_value=kwargs.get("raw_value", Decimal("1.00")),
            user=self.user,
        )

    def test_is_editable_by_status(self):
        pending = self._create_imported(
            reference="p", status=ImportedPayment.IMPORT_STATUS_PENDING
        )
        failed = self._create_imported(
            reference="f", status=ImportedPayment.IMPORT_STATUS_FAILED
        )
        processing = self._create_imported(
            reference="x", status=ImportedPayment.IMPORT_STATUS_PROCESSING
        )

        self.assertTrue(pending.is_editable())
        self.assertTrue(failed.is_editable())
        self.assertFalse(processing.is_editable())

    def test_can_edit_filters_by_user_reference_and_status(self):
        self._create_imported(
            reference="ok", status=ImportedPayment.IMPORT_STATUS_PENDING
        )
        self._create_imported(
            reference="no", status=ImportedPayment.IMPORT_STATUS_PROCESSING
        )

        other_user = User.objects.create_user(username="other-imported", password="123")
        ImportedPayment.objects.create(
            import_source=ImportedPayment.IMPORT_SOURCE_TRANSACTIONS,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_NEW,
            reference="ok",
            status=ImportedPayment.IMPORT_STATUS_PENDING,
            raw_type=Payment.TYPE_DEBIT,
            raw_name="other",
            raw_description="",
            raw_date=date.today(),
            raw_installments=1,
            raw_payment_date=date.today(),
            raw_value=Decimal("1.00"),
            user=other_user,
        )

        self.assertTrue(ImportedPayment.can_edit("ok", self.user))
        self.assertFalse(ImportedPayment.can_edit("no", self.user))
        self.assertFalse(ImportedPayment.can_edit("missing", self.user))
