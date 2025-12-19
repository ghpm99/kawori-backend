from multiprocessing.managers import BaseManager
import time
from invoice.models import Invoice
from payment.models import ImportedPayment
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process Imported Payments"

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

    def process_payment_by_merge(self, payments_to_process):
        # TODO buscar nota target
        # TODO atualizar dados necessarios
        pass

    def process_payment_by_new(self, payments_to_process):
        # TODO criar invoice
        # TODO criar nota
        pass

    def process_payment(self, payments_to_process):
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
