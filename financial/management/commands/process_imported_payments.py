from datetime import timedelta
from decimal import Decimal
import re
import time
from financial.utils import generate_payments, update_invoice_value
from invoice.models import Invoice
from invoice.utils import validate_invoice_data
from payment.models import ImportedPayment, Payment
from payment.utils import generate_payment_installments_by_name
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from tag.models import Tag


class Command(BaseCommand):
    help = "Process Imported Payments"

    INVALID_KEYWORDS = ("iof",)
    PROCESSING_TIMEOUT_MINUTES = 10

    def recover_stuck_processing(self):
        cutoff = timezone.now() - timedelta(minutes=self.PROCESSING_TIMEOUT_MINUTES)
        stuck = ImportedPayment.objects.filter(
            status=ImportedPayment.IMPORT_STATUS_PROCESSING,
            updated_at__lt=cutoff,
        )
        count = stuck.update(
            status=ImportedPayment.IMPORT_STATUS_FAILED,
            status_description="Timeout: processamento excedeu o tempo limite",
        )
        if count:
            print(f"Recovered {count} stuck processing payments")

    def is_processing_running(self) -> bool:
        return ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_PROCESSING).exists()

    def list_to_process(self, limit=100):
        return (
            ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_QUEUED)
            .order_by("id")
            .select_related("matched_payment", "matched_payment__invoice")
            .prefetch_related("matched_payment__invoice__tags", "raw_tags")[:limit]
        )

    def try_set_processing(self, imported_payment_id: int) -> bool:
        updated = ImportedPayment.objects.filter(
            id=imported_payment_id,
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
        ).update(status=ImportedPayment.IMPORT_STATUS_PROCESSING)

        return updated == 1

    def get_merge_group_payments(self, merge_group: str):
        return ImportedPayment.objects.filter(
            status=ImportedPayment.IMPORT_STATUS_QUEUED,
            merge_group=merge_group,
        ).order_by("id")

    def claim_merge_group_payments(self, merge_group: str):
        payment_by_merge_group = self.get_merge_group_payments(merge_group)
        payment_by_merge_group_list = []
        for payment in payment_by_merge_group:
            if not self.try_set_processing(payment.id):
                continue
            payment_by_merge_group_list.append(payment)

        return payment_by_merge_group_list

    def is_auxiliary_payment(self, name: str) -> bool:
        return any(k in name.lower() for k in self.INVALID_KEYWORDS)

    def get_main_payment(self, payments_to_process: list[ImportedPayment]) -> ImportedPayment:

        for payment in payments_to_process:
            if not self.is_auxiliary_payment(payment.raw_name):
                return payment

        raise Exception("Não foi possivel encontrar o pagamento principal")

    def format_brl(self, value: Decimal) -> str:
        return f"R${value:.2f}"

    def get_payment_description(self, payments_to_process: list[ImportedPayment]) -> str:
        return " | ".join(
            f"{payment.raw_description} {self.format_brl(payment.raw_value)}"
            for payment in payments_to_process
            if payment.raw_description and payment.raw_value is not None
        )

    def merge_tags(self, source: list[Tag], target: list[Tag]) -> list[Tag]:
        merged = list(target)
        seen_ids = {tag.id for tag in merged if tag.id is not None}

        for tag in source:
            if tag.id not in seen_ids:
                merged.append(tag)
                seen_ids.add(tag.id)

        return merged

    def finish_with_error(self, error_description: str, payments_to_process: list[ImportedPayment]):
        for payment in payments_to_process:
            payment.status = ImportedPayment.IMPORT_STATUS_FAILED
            payment.status_description = error_description
            payment.save()

    def finish_with_success(self, payments_to_process: list[ImportedPayment]):
        for payment in payments_to_process:
            payment.status = ImportedPayment.IMPORT_STATUS_COMPLETED
            payment.save()

    def update_invoice_by_imported_payment(self, payment: Payment | None, payments_to_process: list[ImportedPayment]):
        if payment is None:
            raise Exception("Pagamento merge sem pagamento selecionado")

        main_payment = self.get_main_payment(payments_to_process)

        payment_description = self.get_payment_description(payments_to_process)
        payment.description = payment_description

        if not payment.reference:
            payment.reference = main_payment.reference

        payment.date = main_payment.raw_date
        payment.payment_date = main_payment.raw_payment_date

        # Update payment value with sum of all imported payments
        total_raw_value = sum(p.raw_value for p in payments_to_process)
        payment.value = total_raw_value

        payment.save()

        # Recalculate invoice totals
        update_invoice_value(payment.invoice)

    def process_payment_by_merge(self, payments_to_process: list[ImportedPayment]):
        payment = next(
            (payment.matched_payment for payment in payments_to_process if payment.matched_payment is not None),
            None,
        )
        self.update_invoice_by_imported_payment(payment, payments_to_process)

    def normalize_invoice_name(self, name: str) -> str:
        if not name:
            return ""

        patterns = [
            r"parcela\s*\d+\s*(?:/|de)\s*\d+",
            r"\b\d+\s*/\s*\d+\b",
        ]

        for pattern in patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        return re.sub(r"\s{2,}", " ", name).strip()

    def get_invoice_name(self, payment: ImportedPayment) -> str:
        name = self.normalize_invoice_name(payment.raw_name)

        if name:
            return name

        payment_name_fallback = f"Pagamento {payment.raw_description} {payment.reference}"

        return payment_name_fallback[:255]

    def create_invoice_by_imported_payment(self, payments_to_process: list[ImportedPayment]):
        main_payment = self.get_main_payment(payments_to_process)
        current_installments = max(
            generate_payment_installments_by_name(payment.raw_name)[0] for payment in payments_to_process
        )
        total_installments = max(
            generate_payment_installments_by_name(payment.raw_name)[1] for payment in payments_to_process
        )
        installments_to_import = total_installments - current_installments + 1
        invoice_name = self.get_invoice_name(main_payment)
        invoice_value = (sum(payment.raw_value for payment in payments_to_process)) * installments_to_import
        invoice = Invoice(
            status=Invoice.STATUS_OPEN,
            type=main_payment.raw_type,
            name=invoice_name,
            date=main_payment.raw_date,
            installments=installments_to_import,
            payment_date=main_payment.raw_payment_date,
            fixed=False,
            active=True,
            value=invoice_value,
            value_open=invoice_value,
            user=main_payment.user,
        )
        invoice.save()
        invoice_tags = []
        for payment in payments_to_process:
            invoice_tags = self.merge_tags(list(payment.raw_tags.all()), invoice_tags)

        invoice.tags.set(invoice_tags)
        return invoice

    def process_payment_by_new(self, payments_to_process: list[ImportedPayment]):
        invoice = self.create_invoice_by_imported_payment(payments_to_process)
        payment_description = self.get_payment_description(payments_to_process)
        generate_payments(invoice, payment_description, payments_to_process[0].reference)
        update_invoice_value(invoice)
        validate_invoice_data(invoice)

    def check_payment_is_merge(self, payment_to_process: ImportedPayment):
        has_merge_strategy = payment_to_process.import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE
        has_payment_matched = payment_to_process.matched_payment is not None

        return has_merge_strategy or has_payment_matched

    def process_payment(self, payments_to_process: list[ImportedPayment]):
        with transaction.atomic():
            has_merge = any(self.check_payment_is_merge(payment) for payment in payments_to_process)
            if has_merge:
                self.process_payment_by_merge(payments_to_process)
            else:
                self.process_payment_by_new(payments_to_process)
            self.finish_with_success(payments_to_process)

    def check_existing_payments(self, payments: list[ImportedPayment]):
        references = {p.reference for p in payments if p.reference}
        user = {p.user for p in payments}
        return Payment.objects.filter(reference__in=references, user__in=user, active=True).exists()

    def run_command(self):
        self.recover_stuck_processing()

        if self.is_processing_running():
            print("Já existe processo executando")
            return

        list_to_process = self.list_to_process()

        for payment_to_process in list_to_process:
            try:
                if not self.try_set_processing(payment_to_process.id):
                    continue

                payments_to_process = [payment_to_process]
                if payment_to_process.merge_group:
                    others = self.claim_merge_group_payments(payment_to_process.merge_group)
                    payments_to_process.extend(others)
                if self.check_existing_payments(payments_to_process):
                    raise Exception("Já existe pagamento cadastrado com a mesma referência")
                self.process_payment(payments_to_process)
            except Exception as e:
                print(e)
                self.finish_with_error(
                    e.__str__(), payments_to_process if payments_to_process else [payment_to_process]
                )

    def handle(self, *args, **options):
        begin = time.time()

        print("Running...")

        self.run_command()

        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
