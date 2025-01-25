import time
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from invoice.models import Invoice


class Command(BaseCommand):
    """
    Create invoice
    """

    def run_command(self):
        invoice = Invoice.objects.filter(id=403).first()
        payment_date = "2023-11-06"
        date_format = "%Y-%m-%d"
        for payment in invoice.payment_set.all():
            payment.payment_date = payment_date
            payment.value = 1206.58
            payment.save()
            date_obj = datetime.strptime(payment_date, date_format)
            future_payment = date_obj + relativedelta(months=1)
            payment_date = future_payment.strftime(date_format)

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
