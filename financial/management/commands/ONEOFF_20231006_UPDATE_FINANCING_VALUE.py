import time
from django.core.management.base import BaseCommand
from financial.models import Payment


class Command(BaseCommand):
    """
        Create invoice
    """

    def run_command(self):
        payments = Payment.objects.filter(invoice=403).order_by('installments').all()
        value = 1209.85
        reduce = 0.014
        for payment in payments:
            if payment.installments < 68:
                continue

            if payment.installments == 87:
                value = 1215.25
                reduce = 0.0244

            if payment.installments == 147:
                value = 1225.81
                reduce = 0.00966

            if payment.installments == 207:
                value = 1240.65
                reduce = 0.1303

            if payment.installments == 267:
                value = 1265.13
                reduce = 0.34237

            if payment.installments == 327:
                value = 1254.23
                reduce = 0.5944

            if payment.installments == 387:
                value = 1236.86
                reduce = 1.83969

            payment.value = round(value, 2)
            payment.save()
            value = value - reduce

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
