import time

from django.core.management.base import BaseCommand

from payment.models import Payment


class Command(BaseCommand):
    """
    Update payment date
    """

    def run_command(self):
        ids_to_update = [
            2241,
            2242,
            2243,
            2244,
            2245,
            2246,
            2247,
            2248,
            2249,
            2250,
            2251,
            2180,
            2252,
            2195,
            2207,
            2068,
            2253,
            2254,
            1981,
            2183,
        ]
        payments = Payment.objects.filter(id__in=ids_to_update).all()
        payment_date = "2026-01-18"
        for payment in payments:
            payment.payment_date = payment_date
            payment.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
