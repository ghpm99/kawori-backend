from decimal import Decimal
from unittest.mock import patch
from django.core.management import call_command
from django.contrib.auth import get_user_model

from django.test import TestCase

from invoice.models import Invoice
from payment.models import ImportedPayment, Payment

User = get_user_model()


class ProcessImportedPaymentsCommandTest(TestCase):

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

        self.assertEqual(invoice.value, Decimal("300.00"))
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
