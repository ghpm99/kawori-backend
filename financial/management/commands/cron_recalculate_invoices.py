import time
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from invoice.models import Invoice
from payment.models import Payment


class Command(BaseCommand):
    help = "Check invoices values"

    def run_command(self):
        for invoice in Invoice.objects.all().iterator(chunk_size=1000):
            invoice_value = 0
            invoice_value_open = 0
            invoice_value_closed = 0

            next_payment_date = None
            for payment in Payment.objects.filter(invoice=invoice.id, active=True).all():
                invoice_value = invoice_value + payment.value
                if payment.status == Payment.STATUS_OPEN:
                    invoice_value_open = invoice_value_open + payment.value
                    if next_payment_date is None or payment.payment_date < next_payment_date:
                        next_payment_date = payment.payment_date
                elif payment.status == Payment.STATUS_DONE:
                    invoice_value_closed = invoice_value_closed + payment.value
            invoice.value = invoice_value
            invoice.value_open = invoice_value_open
            invoice.value_closed = invoice_value_closed
            invoice.payment_date = next_payment_date
            invoice.save()

    def handle(self, *args, **options):
        begin = time.time()

        print("Running...")

        self.run_command()

        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
