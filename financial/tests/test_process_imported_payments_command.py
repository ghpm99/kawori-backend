from decimal import Decimal
from unittest.mock import patch
from django.core.management import call_command
from django.contrib.auth import get_user_model

from django.test import TestCase

from invoice.models import Invoice
from payment.models import ImportedPayment, Payment

User = get_user_model()


class ProcessImportedPaymentsCommandTest(TestCase):

    def assertInvoiceEqual(self, invoice, expected: dict):
        """
        Helper para comparar Invoice persistida no banco com valores esperados.
        """

        # Status e tipo
        self.assertEqual(invoice.status, expected.get("status"))
        self.assertEqual(invoice.type, expected.get("type"))

        # Texto
        self.assertEqual(invoice.name, expected.get("name"))

        # Datas
        if isinstance(expected.get("date"), str):
            self.assertEqual(invoice.date.isoformat(), expected["date"])
        else:
            self.assertEqual(invoice.date, expected.get("date"))

        if isinstance(expected.get("payment_date"), str):
            self.assertEqual(invoice.payment_date.isoformat(), expected["payment_date"])
        else:
            self.assertEqual(invoice.payment_date, expected.get("payment_date"))

        # Numéricos
        self.assertEqual(invoice.installments, expected.get("installments", 1))
        self.assertEqual(invoice.value, expected.get("value", Decimal("0.00")))
        self.assertEqual(invoice.value_open, expected.get("value_open", Decimal("0.00")))
        self.assertEqual(invoice.value_closed, expected.get("value_closed", Decimal("0.00")))

        # Flags
        self.assertEqual(invoice.fixed, expected.get("fixed", False))
        self.assertEqual(invoice.active, expected.get("active", True))

        # Relacionamentos
        if "contract" in expected:
            self.assertEqual(invoice.contract, expected["contract"])
        else:
            self.assertIsNone(invoice.contract)

        if "user" in expected:
            self.assertEqual(invoice.user, expected["user"])

    def assertPaymentEqual(self, payment, expected: dict):
        """
        Helper para comparar Payment persistido no banco com valores esperados.
        """

        self.assertEqual(payment.status, expected.get("status"))
        self.assertEqual(payment.type, expected.get("type"))
        self.assertEqual(payment.name, expected.get("name"))

        # Campos de texto opcionais
        self.assertEqual(payment.description or "", expected.get("description", ""))
        self.assertEqual(payment.reference or "", expected.get("reference", ""))

        # Datas
        if isinstance(expected.get("date"), str):
            self.assertEqual(payment.date.isoformat(), expected["date"])
        else:
            self.assertEqual(payment.date, expected.get("date"))

        if isinstance(expected.get("payment_date"), str):
            self.assertEqual(payment.payment_date.isoformat(), expected["payment_date"])
        else:
            self.assertEqual(payment.payment_date, expected.get("payment_date"))

        # Numéricos
        self.assertEqual(payment.installments, expected.get("installments", 1))
        self.assertEqual(payment.value, expected.get("value", Decimal("0.00")))

        # Flags
        self.assertEqual(payment.fixed, expected.get("fixed", False))
        self.assertEqual(payment.active, expected.get("active", True))

        # Relacionamentos
        if "invoice" in expected:
            self.assertEqual(payment.invoice, expected["invoice"])

        if "user" in expected:
            self.assertEqual(payment.user, expected["user"])

    def setUp(self):
        self.user = User.objects.create_user(username="test", email="test@test.com", password="123")

    def test_command_runs_without_errors(self):
        call_command("process_imported_payments")

    def test_creates_invoice_and_payments(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Notebook Dell Parcela 1/3",
            raw_value=Decimal("300.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.CREDIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()

        self.assertEqual(invoice.value, Decimal("900.00"))
        self.assertEqual(invoice.installments, 3)

    def test_imported_payment_completed(self):
        payment = ImportedPayment.objects.create(
            user=self.user,
            raw_name="Netflix",
            raw_value=Decimal("39.90"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        payment.refresh_from_db()
        self.assertEqual(payment.status, ImportedPayment.IMPORT_STATUS_COMPLETED)

    def test_rollback_on_error(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Erro Teste",
            raw_value=Decimal("100.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        with patch("financial.utils.generate_payments", side_effect=ValueError("Erro forçado")):
            call_command("process_imported_payments")

        self.assertEqual(Invoice.objects.count(), 0)

    def test_merge_group_processing(self):
        p1 = ImportedPayment.objects.create(
            reference="a",
            user=self.user,
            raw_name="Compra X",
            raw_value=Decimal("50.00"),
            merge_group="abc",
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        p2 = ImportedPayment.objects.create(
            reference="b",
            user=self.user,
            raw_name="Compra X",
            raw_value=Decimal("30.00"),
            merge_group="abc",
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(
            ImportedPayment.objects.filter(merge_group="abc", status=ImportedPayment.IMPORT_STATUS_COMPLETED).count(), 2
        )

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_processing_logic(self):
        ImportedPayment.objects.create(
            reference="ref_1",
            user=self.user,
            raw_name="Compra X",
            raw_description="descricao",
            raw_value=Decimal("50.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_COMPLETED).count(), 1)

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        expected_invoice = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Compra X",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("50.00"),
            "value_open": Decimal("50.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Compra X #1",
            "description": "descricao R$50.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("50.00"),
            "user": self.user,
        }

        invoice = Invoice.objects.get()
        self.assertInvoiceEqual(invoice, expected_invoice)

        payment = Payment.objects.get()
        self.assertPaymentEqual(payment, expected_payment)

    def test_create_invoice_already_exist_ref(self):
        invoice_ref = Invoice.objects.create(
            status=Invoice.STATUS_OPEN,
            type=Invoice.Type.DEBIT,
            name="Computador ref",
            date="2025-01-10",
            payment_date="2025-01-10",
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("25.00"),
            value_open=Decimal("25.00"),
            value_closed=Decimal("0.00"),
            contract=None,
            user=self.user,
        )

        Payment.objects.create(
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Computador ref #1",
            description="descricao R$25.00",
            reference="ref_1",
            installments=1,
            date="2025-01-10",
            payment_date="2025-01-10",
            fixed=False,
            active=True,
            value=Decimal("25.00"),
            user=self.user,
            invoice=invoice_ref,
        )

        ImportedPayment.objects.create(
            reference="ref_1",
            user=self.user,
            raw_name="Compra X",
            raw_description="descricao",
            raw_value=Decimal("25.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_COMPLETED).count(), 1)

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        expected_invoice = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Compra X",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("50.00"),
            "value_open": Decimal("50.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Compra X #1",
            "description": "descricao R$50.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("50.00"),
            "user": self.user,
        }

        invoice = Invoice.objects.get()
        self.assertInvoiceEqual(invoice, expected_invoice)

        payment = Payment.objects.get()
        self.assertPaymentEqual(payment, expected_payment)

    def test_create_payments_with_installments(self):
        ImportedPayment.objects.create(
            reference="ref_1",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Notebook Dell Parcela 1/3",
            raw_description="descricao",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("100.00"),
            user=self.user,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()

        expected_invoice = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Notebook Dell",
            "date": "2024-01-10",
            "installments": 3,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("300.00"),
            "value_open": Decimal("300.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment_1 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #1",
            "description": "descricao R$100.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("100.00"),
            "user": self.user,
        }
        expected_payment_2 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #2",
            "description": "descricao R$100.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 2,
            "payment_date": "2024-02-10",
            "fixed": False,
            "active": True,
            "value": Decimal("100.00"),
            "user": self.user,
        }
        expected_payment_3 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #3",
            "description": "descricao R$100.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 3,
            "payment_date": "2024-03-10",
            "fixed": False,
            "active": True,
            "value": Decimal("100.00"),
            "user": self.user,
        }

        self.assertInvoiceEqual(invoice, expected_invoice)

        payment_list = Payment.objects.all()
        self.assertEqual(payment_list.__len__(), 3)

        self.assertPaymentEqual(payment_list[0], expected_payment_1)
        self.assertPaymentEqual(payment_list[1], expected_payment_2)
        self.assertPaymentEqual(payment_list[2], expected_payment_3)
