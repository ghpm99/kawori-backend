from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from invoice.models import Invoice
from payment.models import ImportedPayment, Payment
from tag.models import Tag

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
        self.assertEqual(
            invoice.value_open, expected.get("value_open", Decimal("0.00"))
        )
        self.assertEqual(
            invoice.value_closed, expected.get("value_closed", Decimal("0.00"))
        )

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
        self.user = User.objects.create_user(
            username="test", email="test@test.com", password="123"
        )

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
        imported_payment = ImportedPayment.objects.create(
            user=self.user,
            raw_name="Erro Teste",
            raw_value=Decimal("100.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        with patch(
            "financial.management.commands.process_imported_payments.Invoice.save",
            autospec=True,
            wraps=Invoice.save,
        ) as save_mock, patch(
            "financial.management.commands.process_imported_payments.generate_payments",
            side_effect=ValueError("Erro forçado"),
        ):
            call_command("process_imported_payments")

        imported_payment.refresh_from_db()
        self.assertTrue(save_mock.called)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(imported_payment.status_description, "Erro forçado")
        self.assertEqual(imported_payment.status, ImportedPayment.IMPORT_STATUS_FAILED)

    def test_merge_group_processing(self):
        ImportedPayment.objects.create(
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

        ImportedPayment.objects.create(
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
            ImportedPayment.objects.filter(
                merge_group="abc", status=ImportedPayment.IMPORT_STATUS_COMPLETED
            ).count(),
            2,
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

        self.assertEqual(
            ImportedPayment.objects.filter(
                status=ImportedPayment.IMPORT_STATUS_COMPLETED
            ).count(),
            1,
        )

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

        self.assertEqual(
            ImportedPayment.objects.filter(
                status=ImportedPayment.IMPORT_STATUS_FAILED
            ).count(),
            1,
        )

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        expected_invoice = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Computador ref",
            "date": "2025-01-10",
            "installments": 1,
            "payment_date": "2025-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("25.00"),
            "value_open": Decimal("25.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Computador ref #1",
            "description": "descricao R$25.00",
            "reference": "ref_1",
            "date": "2025-01-10",
            "installments": 1,
            "payment_date": "2025-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("25.00"),
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

    def test_create_payments_with_paid_installments(self):
        ImportedPayment.objects.create(
            reference="ref_1",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Notebook Dell Parcela 10/12",
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

    def test_create_payment_with_one_installments(self):
        ImportedPayment.objects.create(
            reference="ref_1",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Notebook Dell Parcela 1/1",
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
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("100.00"),
            "value_open": Decimal("100.00"),
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

        self.assertInvoiceEqual(invoice, expected_invoice)

        payment_list = Payment.objects.all()
        self.assertEqual(payment_list.__len__(), 1)

        self.assertPaymentEqual(payment_list[0], expected_payment_1)

    def test_create_payments_installments_with_iof(self):
        ImportedPayment.objects.create(
            reference="ref_1",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Notebook Dell Parcela 10/12",
            raw_description="descricao",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("100.00"),
            user=self.user,
        )

        ImportedPayment.objects.create(
            reference="ref_2",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="IOF Dell Parcela",
            raw_description="IOF",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("50.00"),
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
            "value": Decimal("450.00"),
            "value_open": Decimal("450.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment_1 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #1",
            "description": "descricao R$100.00 | IOF R$50.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("150.00"),
            "user": self.user,
        }
        expected_payment_2 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #2",
            "description": "descricao R$100.00 | IOF R$50.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 2,
            "payment_date": "2024-02-10",
            "fixed": False,
            "active": True,
            "value": Decimal("150.00"),
            "user": self.user,
        }
        expected_payment_3 = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Notebook Dell #3",
            "description": "descricao R$100.00 | IOF R$50.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 3,
            "payment_date": "2024-03-10",
            "fixed": False,
            "active": True,
            "value": Decimal("150.00"),
            "user": self.user,
        }

        self.assertInvoiceEqual(invoice, expected_invoice)

        payment_list = Payment.objects.all()
        self.assertEqual(payment_list.__len__(), 3)

        self.assertPaymentEqual(payment_list[0], expected_payment_1)
        self.assertPaymentEqual(payment_list[1], expected_payment_2)
        self.assertPaymentEqual(payment_list[2], expected_payment_3)

    def test_create_multiple_merge_group(self):

        ImportedPayment.objects.create(
            reference="ref_1",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Pagamento Parcela 1/2",
            raw_description="descricao1",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("1.00"),
            user=self.user,
        )

        ImportedPayment.objects.create(
            reference="ref_2",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Pagamento Parcela 5/8",
            raw_description="descricao2",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("1.00"),
            user=self.user,
        )

        ImportedPayment.objects.create(
            reference="ref_3",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Pagamento Parcela 3/5",
            raw_description="descricao3",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("1.00"),
            user=self.user,
        )

        ImportedPayment.objects.create(
            reference="ref_4",
            merge_group="abc",
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            raw_type=Invoice.Type.DEBIT,
            raw_name="Pagamento Parcela 12/12",
            raw_description="descricao4",
            raw_date="2024-01-10",
            raw_installments=1,
            raw_payment_date="2024-01-10",
            raw_value=Decimal("1.00"),
            user=self.user,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()

        expected_invoice = {
            "status": Invoice.STATUS_OPEN,
            "type": Invoice.Type.DEBIT,
            "name": "Pagamento",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("4.00"),
            "value_open": Decimal("4.00"),
            "value_closed": Decimal("0.00"),
            "contract": None,
            "user": self.user,
        }

        expected_payment = {
            "status": Payment.STATUS_OPEN,
            "type": Payment.TYPE_DEBIT,
            "name": "Pagamento #1",
            "description": "descricao1 R$1.00 | descricao2 R$1.00 | descricao3 R$1.00 | descricao4 R$1.00",
            "reference": "ref_1",
            "date": "2024-01-10",
            "installments": 1,
            "payment_date": "2024-01-10",
            "fixed": False,
            "active": True,
            "value": Decimal("4.00"),
            "user": self.user,
        }

        self.assertInvoiceEqual(invoice, expected_invoice)

        payment_list = Payment.objects.all()
        self.assertEqual(payment_list.__len__(), 1)

        self.assertPaymentEqual(payment_list[0], expected_payment)

    def test_ignore_non_queued_imported_payment(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Compra Ignorada",
            raw_value=Decimal("100.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_COMPLETED,
        )

        call_command("process_imported_payments")

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_multiple_merge_groups_generate_separate_invoices(self):
        ImportedPayment.objects.create(
            user=self.user,
            reference="a",
            merge_group="a",
            raw_name="Compra A",
            raw_value=Decimal("10.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        ImportedPayment.objects.create(
            user=self.user,
            reference="b",
            merge_group="b",
            raw_name="Compra B",
            raw_value=Decimal("20.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(Invoice.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 2)

    def test_iof_only_does_not_create_invoice(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="IOF Cartão",
            raw_description="IOF",
            raw_value=Decimal("5.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_empty_name_uses_fallback(self):
        ImportedPayment.objects.create(
            user=self.user,
            reference="abc",
            raw_name="",
            raw_description="descricao",
            raw_value=Decimal("10.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()
        self.assertTrue(invoice.name)
        self.assertEqual(invoice.name, "Pagamento descricao abc")

    def test_negative_value_payment_is_ignored(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Compra Zero",
            raw_value=Decimal("-1.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_invalid_installment_fallbacks_to_single_payment(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Compra Parcela 3/2",
            raw_value=Decimal("100.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()
        self.assertEqual(invoice.installments, 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_payment_invoice_relationship(self):
        ImportedPayment.objects.create(
            user=self.user,
            raw_name="Compra X",
            raw_value=Decimal("50.00"),
            raw_installments=1,
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()
        payment = Payment.objects.get()

        self.assertEqual(payment.invoice, invoice)

    def test_assert_helpers_cover_non_string_dates_and_invoice_contract_branches(self):
        invoice = Invoice.objects.create(
            status=Invoice.STATUS_OPEN,
            type=Invoice.Type.DEBIT,
            name="Helper Invoice",
            date=date(2026, 1, 10),
            payment_date=date(2026, 1, 10),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            value_closed=Decimal("0.00"),
            contract=None,
            user=self.user,
        )
        payment = Payment.objects.create(
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Helper Payment",
            description="",
            reference="helper",
            installments=1,
            date=date(2026, 1, 10),
            payment_date=date(2026, 1, 10),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            user=self.user,
            invoice=invoice,
        )

        self.assertInvoiceEqual(
            invoice,
            {
                "status": invoice.status,
                "type": invoice.type,
                "name": invoice.name,
                "date": invoice.date,
                "installments": invoice.installments,
                "payment_date": invoice.payment_date,
                "fixed": invoice.fixed,
                "active": invoice.active,
                "value": invoice.value,
                "value_open": invoice.value_open,
                "value_closed": invoice.value_closed,
            },
        )

        self.assertPaymentEqual(
            payment,
            {
                "status": payment.status,
                "type": payment.type,
                "name": payment.name,
                "description": payment.description,
                "reference": payment.reference,
                "date": payment.date,
                "installments": payment.installments,
                "payment_date": payment.payment_date,
                "fixed": payment.fixed,
                "active": payment.active,
                "value": payment.value,
                "invoice": invoice,
                "user": self.user,
            },
        )

    def test_merge_updates_payment_value_and_invoice(self):
        """Testa que merge atualiza o valor do Payment e recalcula a Invoice"""
        # Criar invoice e payment existentes
        invoice = Invoice.objects.create(
            status=Invoice.STATUS_OPEN,
            type=Invoice.Type.DEBIT,
            name="Discord",
            date="2024-01-10",
            payment_date="2024-02-10",
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            value_open=Decimal("0.00"),
            value_closed=Decimal("0.00"),
            user=self.user,
        )

        existing_payment = Payment.objects.create(
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Discord #1",
            description="",
            reference="",
            installments=1,
            date="2024-01-10",
            payment_date="2024-02-10",
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            user=self.user,
            invoice=invoice,
        )

        # Criar ImportedPayment principal (Discord)
        ImportedPayment.objects.create(
            reference="ref_discord",
            merge_group="discord_mg",
            user=self.user,
            raw_name="Discord",
            raw_description="Discord",
            raw_value=Decimal("30.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-02-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_MERGE,
            matched_payment=existing_payment,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        # Criar ImportedPayment IOF no mesmo merge_group
        ImportedPayment.objects.create(
            reference="ref_iof_discord",
            merge_group="discord_mg",
            user=self.user,
            raw_name="IOF Discord",
            raw_description="IOF",
            raw_value=Decimal("2.50"),
            raw_date="2024-01-10",
            raw_payment_date="2024-02-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_MERGE,
            matched_payment=existing_payment,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        # Verificar que o payment foi atualizado com o valor total (30.00 + 2.50)
        existing_payment.refresh_from_db()
        self.assertEqual(existing_payment.value, Decimal("32.50"))
        self.assertEqual(existing_payment.description, "Discord R$30.00 | IOF R$2.50")

        # Verificar que a invoice foi recalculada
        invoice.refresh_from_db()
        self.assertEqual(invoice.value, Decimal("32.50"))
        self.assertEqual(invoice.value_open, Decimal("32.50"))

        # Verificar que ambos ImportedPayments estão COMPLETED
        self.assertEqual(
            ImportedPayment.objects.filter(
                merge_group="discord_mg", status=ImportedPayment.IMPORT_STATUS_COMPLETED
            ).count(),
            2,
        )

    def test_merge_single_payment_updates_value(self):
        """Testa que merge de um único pagamento (sem merge_group) atualiza o valor"""
        invoice = Invoice.objects.create(
            status=Invoice.STATUS_OPEN,
            type=Invoice.Type.DEBIT,
            name="Netflix",
            date="2024-01-10",
            payment_date="2024-02-10",
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            value_open=Decimal("0.00"),
            value_closed=Decimal("0.00"),
            user=self.user,
        )

        existing_payment = Payment.objects.create(
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Netflix #1",
            description="",
            reference="",
            installments=1,
            date="2024-01-10",
            payment_date="2024-02-10",
            fixed=False,
            active=True,
            value=Decimal("0.00"),
            user=self.user,
            invoice=invoice,
        )

        ImportedPayment.objects.create(
            reference="ref_netflix",
            user=self.user,
            raw_name="Netflix",
            raw_description="Netflix",
            raw_value=Decimal("39.90"),
            raw_date="2024-01-10",
            raw_payment_date="2024-02-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            import_strategy=ImportedPayment.IMPORT_STRATEGY_MERGE,
            matched_payment=existing_payment,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        existing_payment.refresh_from_db()
        self.assertEqual(existing_payment.value, Decimal("39.90"))

        invoice.refresh_from_db()
        self.assertEqual(invoice.value, Decimal("39.90"))
        self.assertEqual(invoice.value_open, Decimal("39.90"))

    def test_processing_timeout_recovery(self):
        """Testa que pagamentos travados em PROCESSING são recuperados como FAILED"""
        stuck_payment = ImportedPayment.objects.create(
            user=self.user,
            raw_name="Travado",
            raw_value=Decimal("100.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,
        )

        # Forçar updated_at para 15 minutos atrás (acima do timeout de 10)
        ImportedPayment.objects.filter(id=stuck_payment.id).update(
            updated_at=timezone.now() - timedelta(minutes=15)
        )

        call_command("process_imported_payments")

        stuck_payment.refresh_from_db()
        self.assertEqual(stuck_payment.status, ImportedPayment.IMPORT_STATUS_FAILED)
        self.assertIn("Timeout", stuck_payment.status_description)

    def test_processing_timeout_does_not_affect_recent(self):
        """Testa que pagamentos PROCESSING recentes NÃO são resetados"""
        recent_payment = ImportedPayment.objects.create(
            user=self.user,
            raw_name="Recente",
            raw_value=Decimal("100.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,
        )

        # updated_at é auto_now, então já é recente

        call_command("process_imported_payments")

        recent_payment.refresh_from_db()
        # Deve continuar PROCESSING (não foi recuperado)
        self.assertEqual(
            recent_payment.status, ImportedPayment.IMPORT_STATUS_PROCESSING
        )

    @patch(
        "financial.management.commands.process_imported_payments.suggest_payment_normalization"
    )
    def test_uses_ai_normalization_when_available(self, mocked_normalization):
        suggested_tag = Tag.objects.create(
            name="Mercado", color="#123456", user=self.user
        )
        mocked_normalization.return_value = {
            "normalized_name": "Mercado Central",
            "normalized_description": "Compra consolidada mercado.",
            "installments_total": 1,
            "tag_names": ["Mercado"],
        }

        ImportedPayment.objects.create(
            reference="ref-ai-1",
            user=self.user,
            raw_name="Mercado Central parcela 1/1",
            raw_description="compra mercado",
            raw_value=Decimal("80.00"),
            raw_date="2024-01-10",
            raw_payment_date="2024-01-10",
            raw_installments=1,
            raw_type=Invoice.Type.DEBIT,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        )

        call_command("process_imported_payments")

        invoice = Invoice.objects.get()
        payment = Payment.objects.get()
        self.assertEqual(invoice.name, "Mercado Central")
        self.assertEqual(payment.description, "Compra consolidada mercado.")
        self.assertIn(suggested_tag.id, list(invoice.tags.values_list("id", flat=True)))
