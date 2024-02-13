import time
from django.core.management.base import BaseCommand
from financial.models import Contract, Invoice, Payment


class Command(BaseCommand):
    """
        Create invoice
    """

    def run_command(self):
        payments = Payment.objects.all().order_by('id')
        for payment in payments:
            invoice = Invoice.objects.filter(name=payment.name).first()

            value_open = 0
            value_closed = 0

            if payment.status == Payment.STATUS_OPEN:
                value_open = payment.value
            if payment.status == Payment.STATUS_DONE:
                value_closed = payment.value

            if invoice is None:
                contract = Contract(
                    name=payment.name,
                    value=payment.value,
                    value_open=value_open,
                    value_closed=value_closed
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
                    value_open=value_open,
                    value_closed=value_closed,
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
                    value_open=value_open,
                    value_closed=value_closed,
                    contract=invoice.contract
                )
                invoice.save()
                payment.invoice = invoice
                payment.save()
                continue

            payment.invoice = invoice
            payment.save()
            invoice.value = invoice.value + payment.value
            invoice.value_open = invoice.value_open + value_open
            invoice.value_closed = invoice.value_closed + value_closed
            invoice.installments = invoice.installments + 1
            invoice.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
