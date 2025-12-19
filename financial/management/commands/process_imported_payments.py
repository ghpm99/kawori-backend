from decimal import Decimal
from multiprocessing.managers import BaseManager
import re
import time
from invoice.models import Invoice
from payment.models import ImportedPayment
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process Imported Payments"

    INVALID_KEYWORDS = ("iof",)

    def is_processing_running(self) -> bool:
        return ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_PROCESSING).exists()

    def list_to_process(self, limit=1):
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

    def generate_payment_installments_by_name(self, name: str) -> tuple[int, int]:
        if not name:
            return (1, 1)
        match = re.search(r"parcela\s*(\d+)\s*(?:/|de)\s*(\d+)", name, re.IGNORECASE)
        if match:
            try:
                current = int(match.group(1))
                total = int(match.group(2))
                if current >= 1 and total >= current:
                    return (current, total)
            except ValueError:
                pass

        match = re.search(r"(\d+)\s*/\s*(\d+)", name)
        if match:
            try:
                current = int(match.group(1))
                total = int(match.group(2))
                if current >= 1 and total >= current:
                    return (current, total)
            except ValueError:
                pass

        return (1, 1)

    def is_auxiliary_payment(self, name: str) -> bool:
        return any(k in name.lower() for k in self.INVALID_KEYWORDS)

    def get_valid_name_by_list(self, payments_to_process: list[ImportedPayment]) -> str:
        if not payments_to_process:
            return ""

        for payment in payments_to_process:
            if not self.is_auxiliary_payment(payment.raw_name):
                return payment.raw_name

        return payments_to_process[0].raw_name

    def format_brl(self, value: Decimal) -> str:
        return f"R${value:.2f}"

    def get_payment_description(self, payments_to_process: list[ImportedPayment]) -> str:
        return " | ".join(
            f"{payment.raw_description} {self.format_brl(payment.raw_value)}"
            for payment in payments_to_process
            if payment.raw_description and payment.raw_value is not None
        )

    def process_payment_by_merge(self, payments_to_process: list[ImportedPayment]):
        # TODO buscar nota target
        # TODO atualizar dados necessarios
        pass

    def process_payment_by_new(self, payments_to_process: list[ImportedPayment]):
        max_installments = max(
            self.generate_payment_installments_by_name(payment.raw_name)[1] for payment in payments_to_process
        )
        payment_name = self.get_valid_name_by_list(payments_to_process)
        payment_description = self.get_payment_description(payments_to_process)
        # TODO criar invoice
        # TODO criar nota
        pass

    def process_payment(self, payments_to_process: list[ImportedPayment]):
        has_merge = any(
            payment.import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE for payment in payments_to_process
        )
        if has_merge:
            self.process_payment_by_merge(payments_to_process)
        else:
            self.process_payment_by_new(payments_to_process)

    def run_command(self):
        if self.is_processing_running():
            print("Já existe processo executando")
            return

        list_to_process = self.list_to_process()

        for payment_to_process in list_to_process:
            if not self.try_set_processing(payment_to_process.id):
                continue
            payments_to_process = [payment_to_process]
            if payment_to_process.merge_group:
                others = self.claim_merge_group_payments(payment_to_process.merge_group)
                payments_to_process.extend(others)

            self.process_payment(payments_to_process)

    def handle(self, *args, **options):
        begin = time.time()

        print("Running...")

        self.run_command()

        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
