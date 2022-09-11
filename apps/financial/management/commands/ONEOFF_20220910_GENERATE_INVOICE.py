import time
from django.core.management.base import BaseCommand
from facetexture.models import PreviewBackground
from financial.models import Contract, Invoice, Payment


class Command(BaseCommand):
    """
        Create invoice
    """

    def run_command(self):
        payments = Payment.objects.all().order_by('id')
        for payment in payments:
            invoice = Invoice.objects.filter(name=payment.name).first()
            if invoice is None:
                contract = Contract(
                    name=payment.name
                )
                contract.save()
                invoice = Invoice(
                    status=payment.status,
                    type=payment.type,
                    name=payment.name,
                    date=payment.date,
                    installments=1,
                    payment_date=payment.payment_date,
                    fixed=payment.fixed,
                    active=payment.active,
                    value=payment.value,
                    contract=contract
                )
                invoice.save()
                payment.invoice = invoice
                payment.save()
                continue

            if payment.fixed:
                invoice = Invoice(
                    status=payment.status,
                    type=payment.type,
                    name=payment.name,
                    date=payment.date,
                    installments=1,
                    payment_date=payment.payment_date,
                    fixed=payment.fixed,
                    active=payment.active,
                    value=payment.value,
                    contract=invoice.contract
                )
                invoice.save()
                payment.invoice = invoice
                payment.save()
                continue

            payment.invoice = invoice
            payment.save()
            invoice.value = invoice.value + payment.value
            invoice.installments = invoice.installments + 1
            invoice.save()


    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
