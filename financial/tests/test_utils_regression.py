from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from contract.models import Contract
from financial.utils import (
    calculate_installments,
    generate_payments,
    update_contract_value,
    update_invoice_value,
)
from invoice.models import Invoice
from payment.models import Payment


class FinancialUtilsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="financial-utils", password="123")

    def _create_contract(self, name="Contract U"):
        return Contract.objects.create(name=name, user=self.user)

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            type=kwargs.get("type", Invoice.Type.DEBIT),
            name=kwargs.get("name", "Invoice U"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 10)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("0.00")),
            value_open=kwargs.get("value_open", Decimal("0.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            contract=kwargs.get("contract"),
            user=self.user,
        )

    def _create_payment(self, invoice, **kwargs):
        return Payment.objects.create(
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Payment U"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", ""),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 10)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            status=kwargs.get("status", Payment.STATUS_OPEN),
            invoice=invoice,
            user=self.user,
        )

    def test_calculate_installments_single(self):
        self.assertEqual(calculate_installments(100.0, 1), [100.0])

    def test_calculate_installments_multiple_with_rounding(self):
        values = calculate_installments(100.0, 3)
        self.assertEqual(values, [33.33, 33.33, 33.34])
        self.assertAlmostEqual(sum(values), 100.0, places=2)

    def test_generate_payments_creates_installments_and_reference_only_first(self):
        invoice = self._create_invoice(
            name="Phone",
            installments=3,
            payment_date=date(2026, 2, 15),
            value=Decimal("300.00"),
            value_open=Decimal("300.00"),
            fixed=True,
            type=Invoice.Type.CREDIT,
        )

        generate_payments(invoice, description="desc", reference="ref-123")

        payments = list(
            Payment.objects.filter(invoice=invoice).order_by("installments")
        )
        self.assertEqual(len(payments), 3)
        self.assertEqual(
            [p.name for p in payments], ["Phone #1", "Phone #2", "Phone #3"]
        )
        self.assertEqual(
            [p.value for p in payments],
            [Decimal("100.00"), Decimal("100.00"), Decimal("100.00")],
        )
        self.assertEqual(
            [p.payment_date for p in payments],
            [date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)],
        )
        self.assertEqual(payments[0].reference, "ref-123")
        self.assertEqual(payments[1].reference, "ref-123")
        self.assertEqual(payments[2].reference, "ref-123")

    def test_update_invoice_value_updates_open_closed_and_next_payment_date(self):
        invoice = self._create_invoice(name="Energy", payment_date=date(2026, 1, 1))
        self._create_payment(
            invoice=invoice,
            payment_date=date(2026, 1, 20),
            value=Decimal("20.00"),
            status=Payment.STATUS_OPEN,
        )
        self._create_payment(
            invoice=invoice,
            payment_date=date(2026, 1, 10),
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
        )
        self._create_payment(
            invoice=invoice,
            payment_date=date(2026, 1, 5),
            value=Decimal("5.00"),
            status=Payment.STATUS_DONE,
        )
        self._create_payment(
            invoice=invoice,
            payment_date=date(2026, 1, 2),
            value=Decimal("999.00"),
            status=Payment.STATUS_OPEN,
            active=False,
        )

        update_invoice_value(invoice)
        invoice.refresh_from_db()

        self.assertEqual(invoice.value, Decimal("35.00"))
        self.assertEqual(invoice.value_open, Decimal("30.00"))
        self.assertEqual(invoice.value_closed, Decimal("5.00"))
        self.assertEqual(invoice.status, Invoice.STATUS_OPEN)
        self.assertEqual(invoice.payment_date, date(2026, 1, 10))

    def test_update_invoice_value_sets_done_when_open_is_zero(self):
        invoice = self._create_invoice(
            name="Closed invoice", payment_date=date(2026, 1, 30)
        )
        self._create_payment(
            invoice=invoice,
            payment_date=date(2026, 1, 10),
            value=Decimal("15.00"),
            status=Payment.STATUS_DONE,
        )

        update_invoice_value(invoice)
        invoice.refresh_from_db()

        self.assertEqual(invoice.value, Decimal("15.00"))
        self.assertEqual(invoice.value_open, Decimal("0.00"))
        self.assertEqual(invoice.value_closed, Decimal("15.00"))
        self.assertEqual(invoice.status, Invoice.STATUS_DONE)
        # sem pagamentos em aberto, mantém data atual
        self.assertEqual(invoice.payment_date, date(2026, 1, 30))

    def test_update_contract_value_aggregates_active_invoices_only(self):
        contract = self._create_contract("Main contract")

        active_invoice_1 = self._create_invoice(
            name="A1",
            contract=contract,
            active=True,
            payment_date=date(2026, 1, 5),
        )
        active_invoice_2 = self._create_invoice(
            name="A2",
            contract=contract,
            active=True,
            payment_date=date(2026, 1, 8),
        )
        self._create_invoice(
            name="Inactive",
            contract=contract,
            active=False,
        )

        self._create_payment(
            invoice=active_invoice_1, value=Decimal("10.00"), status=Payment.STATUS_OPEN
        )
        self._create_payment(
            invoice=active_invoice_1, value=Decimal("5.00"), status=Payment.STATUS_DONE
        )
        self._create_payment(
            invoice=active_invoice_2, value=Decimal("20.00"), status=Payment.STATUS_OPEN
        )

        update_contract_value(contract)

        contract.refresh_from_db()
        active_invoice_1.refresh_from_db()
        active_invoice_2.refresh_from_db()

        self.assertEqual(contract.value, Decimal("35.00"))
        self.assertEqual(contract.value_open, Decimal("30.00"))
        self.assertEqual(contract.value_closed, Decimal("5.00"))
        self.assertEqual(active_invoice_1.value, Decimal("15.00"))
        self.assertEqual(active_invoice_2.value, Decimal("20.00"))
