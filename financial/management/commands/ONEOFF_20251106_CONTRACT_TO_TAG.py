import random
import time

from django.core.management.base import BaseCommand

from contract.models import Contract
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class Command(BaseCommand):
    """
    Create Tag and remove contract
    """

    colors = [
        {"id": 0, "color": "#4d8e66"},
        {"id": 1, "color": "#4d8e66"},
        {"id": 2, "color": "#bc433b"},
        {"id": 3, "color": "#3f7398"},
        {"id": 4, "color": "#a166b9"},
        {"id": 5, "color": "#92abe4"},
        {"id": 6, "color": "#243852"},
        {"id": 7, "color": "#314f97"},
        {"id": 8, "color": "#689a94"},
        {"id": 9, "color": "#a64047"},
        {"id": 10, "color": "#506ba4"},
        {"id": 11, "color": "#6e3913"},
        {"id": 12, "color": "#4c8ec0"},
        {"id": 13, "color": "#bf3e3e"},
        {"id": 14, "color": "#998758"},
        {"id": 15, "color": "#52a98d"},
        {"id": 16, "color": "#875023"},
        {"id": 17, "color": "#245237"},
        {"id": 18, "color": "#7f69e1"},
        {"id": 19, "color": "#cc4d4d"},
        {"id": 20, "color": "#43b5ca"},
        {"id": 21, "color": "#a9844e"},
        {"id": 22, "color": "#5f0000"},
        {"id": 23, "color": "#8b76d7"},
        {"id": 24, "color": "#4a6272"},
        {"id": 25, "color": "#767ae9"},
        {"id": 27, "color": "#522824"},
        {"id": 26, "color": "#ffa8ef"},
        {"id": 28, "color": "#92abe4"},
    ]

    def run_command(self):
        contract_list = Contract.objects.all()

        for contract in contract_list:
            print("processing", contract.name)

            # Obtém ou cria a tag equivalente ao contrato
            tag, created = Tag.objects.get_or_create(
                name=contract.name,
                user=contract.user,
                defaults={"color": self.colors[random.randint(0, self.colors.__len__())]},
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
