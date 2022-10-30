import locale
import time
from datetime import datetime, timedelta
from django.conf import settings

from django.core.management.base import BaseCommand
from django.db import connection
import requests

from financial.models import Payment


class Command(BaseCommand):
    help = "Send payment Discord notify"

    def send_discord(self, final_date):

        query_payments = """
            SELECT
                id,
                type,
                name,
                payment_date,
                value
            FROM
                financial_payment fp
            WHERE
                0 = 0
                AND (fp.payment_date AT TIME ZONE 'Brazil/East')::DATE <= %(final_date)s
                AND fp.status = 0
                AND fp.active = TRUE;
        """

        filters = {
            'final_date': final_date
        }

        with connection.cursor() as cursor:
            cursor.execute(query_payments, filters)
            payments_list = cursor.fetchall()

        url = settings.BASE_URL_WEBHOOK + '/financial'

        for item in payments_list:

            type = Payment.TYPES[item[1]]

            json = {
                'id': item[0],
                'type': type[1],
                'name': item[2],
                'payment_date': datetime.strptime(str(item[3]), "%Y-%m-%d").strftime("%d/%m/%Y"),
                'value': float(item[4]),
                'payment': settings.BASE_URL_FRONTEND + '/admin/financial/payments/details/' + str(item[0])
            }

            print(json)
            response = requests.post(url, json=json)
            print(response)

    def run_command(self):

        # locale.setlocale(locale.LC_MONETARY, 'pt_BR.utf8')
        date_referrer = datetime.now().date()

        final_date = date_referrer + timedelta(days=3)

        print('Final date: {}'.format(final_date))
        print('Sending payments to Discord')
        self.send_discord(final_date)

    def handle(self, *args, **options):
        begin = time.time()

        print('Running...')

        self.run_command()

        print('\nSuccess! :)')
        print(f'Done with {time.time() - begin}s')
