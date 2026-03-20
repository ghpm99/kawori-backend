import random
import time

from django.core.management.base import BaseCommand

from contract.models import Contract
from invoice.models import Invoice
from tag.models import Tag


class Command(BaseCommand):
    """
    Create Tag and remove contract
    """

    colors = [
        "#4d8e66",
        "#4d8e66",
        "#bc433b",
        "#3f7398",
        "#a166b9",
        "#92abe4",
        "#243852",
        "#314f97",
        "#689a94",
        "#a64047",
        "#506ba4",
        "#6e3913",
        "#4c8ec0",
        "#bf3e3e",
        "#998758",
        "#52a98d",
        "#875023",
        "#245237",
        "#7f69e1",
        "#cc4d4d",
        "#43b5ca",
        "#a9844e",
        "#5f0000",
        "#8b76d7",
        "#4a6272",
        "#767ae9",
        "#522824",
        "#ffa8ef",
        "#92abe4",
    ]

    def run_command(self):
        contract_list = Contract.objects.all()

        for contract in contract_list:
            print("processing", contract.name)

            # Obtém ou cria a tag equivalente ao contrato
            tag, created = Tag.objects.get_or_create(
                name=contract.name,
                user=contract.user,
                defaults={
                    "color": self.colors[
                        random.randint(0, self.colors.__len__())  # nosec
                    ]
                },
            )

            if created:
                print(f"Tag criada: {tag.name}")
            else:
                print(f"Tag já existente: {tag.name}")

            # Pega as invoices ligadas ao contrato
            invoice_list = Invoice.objects.filter(contract=contract, user=contract.user)

            for invoice in invoice_list:
                if not invoice.tags.filter(id=tag.id).exists():
                    invoice.tags.add(tag)
                    print("Invoice atualizada:", invoice.name)

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
