import time

from django.core.management.base import BaseCommand

from contract.models import Contract
from payment.models import Payment
from tag.models import Tag


class Command(BaseCommand):
    """
    Create Tag and remove contract
    """

    def run_command(self):
        contract_list = Contract.objects.all()
        for contract in contract_list:
            tag = Tag.objects.filter(name=contract.name, user=contract.user).first()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
