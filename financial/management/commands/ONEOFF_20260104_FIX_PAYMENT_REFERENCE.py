import time

from django.core.management.base import BaseCommand

from payment.models import Payment


class Command(BaseCommand):
    """
    Update payment date
    """

    def run_command(self):

        payment = Payment.objects.filter(id=2066).first()
        payment.description = ""
        payment.reference = ""
        payment.save()

        payment = Payment.objects.filter(id=2067).first()
        payment.description = "Mercadolivre*8produtos - Parcela 3/6 R$31.82"
        payment.reference = (
            "ref_bb6e572860d80e95c036186a4ab4b80832a3baf657ff519f5311a62104071396"
        )
        payment.save()

        payment = Payment.objects.filter(id=2068).first()
        payment.description = "Mercadolivre*8produtos - Parcela 4/6 R$31.82"
        payment.reference = (
            "ref_b22c2cc97eebe096cf2dfd3b0a3dda867041a6685ab75cca9a9ffba7124c3972"
        )
        payment.payment_date = "2025-12-18"
        payment.save()

        payment = Payment.objects.filter(id=2069).first()
        payment.description = "Mercadolivre*8produtos - Parcela 5/6 R$31.82"
        payment.reference = (
            "ref_321da9bb62d15cf613b12a576eefd2fb05e6ae9f8424c684f3af9f4a4129fc8d"
        )
        payment.save()

        payment = Payment.objects.filter(id=1979).first()
        payment.description = ""
        payment.reference = ""
        payment.save()

        payment = Payment.objects.filter(id=1980).first()
        payment.description = "Exitlag - Parcela 6/12 R$11.63"
        payment.reference = (
            "ref_7092da55c215600578f3e5f4d4a608de8e23e2e1596d27dcc8bada508ca4087a"
        )
        payment.save()

        payment = Payment.objects.filter(id=1981).first()
        payment.description = "Exitlag - Parcela 7/12 R$11.63"
        payment.reference = (
            "ref_cd22cb449be6e6156a6ddf9042d5d8a9707fc3e72bd6c80784546292c66b491c"
        )
        payment.payment_date = "2025-12-18"
        payment.save()

        payment = Payment.objects.filter(id=1982).first()
        payment.description = "Exitlag - Parcela 8/12 R$11.63"
        payment.reference = (
            "ref_40b1656c2a437d93ca924d31f24fda02c93f1c29e65befbe722f5a2440090c31"
        )
        payment.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
