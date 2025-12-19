import time
from payment.models import ImportedPayment
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process Imported Payments"

    def list_all_imported_payment_to_process(self):
        return ImportedPayment.objects.filter(status=ImportedPayment.IMPORT_STATUS_QUEUED)

    def run_command(self):
        if ImportedPayment.is_processing_running():
            print("Já existe processo executando")
            return

        list_to_process = self.list_all_imported_payment_to_process()

    def handle(self, *args, **options):
        begin = time.time()

        print("Running...")

        self.run_command()

        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
