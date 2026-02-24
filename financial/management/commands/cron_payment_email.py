import time
from datetime import datetime, timedelta
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.template.loader import render_to_string

from payment.models import Payment


class Command(BaseCommand):
    help = "Send payment email notifications"

    def send_email(self, final_date):
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

        filters = {"final_date": final_date}

        with connection.cursor() as cursor:
            cursor.execute(query_payments, filters)
            payments_list = cursor.fetchall()

        if not payments_list:
            print("No payments found to notify")
            return

        payments = []
        total_value = 0

        for item in payments_list:
            type = Payment.TYPES[item[1]]
            payment_value = float(item[4])
            total_value += payment_value

            payments.append(
                {
                    "id": item[0],
                    "type": type[1],
                    "name": item[2],
                    "payment_date": datetime.strptime(str(item[3]), "%Y-%m-%d").strftime("%d/%m/%Y"),
                    "value": payment_value,
                    "payment_url": settings.BASE_URL_FRONTEND + "/admin/financial/payments/details/" + str(item[0]),
                }
            )

        # Render HTML email template
        html_content = render_to_string('payment_email_template.html', {
            'payments': payments,
            'total_value': total_value,
            'final_date': final_date.strftime("%d/%m/%Y"),
        })

        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Notificação de Pagamentos - Vencimento até {final_date.strftime("%d/%m/%Y")}'
        msg['From'] = settings.EMAIL_HOST_USER
        msg['To'] = settings.NOTIFICATION_EMAIL

        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        # Send email
        try:
            with SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
                server.starttls()
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                server.send_message(msg)
            print(f"Email sent successfully to {settings.NOTIFICATION_EMAIL}")
        except Exception as e:
            print(f"Error sending email: {str(e)}")

    def run_command(self):
        date_referrer = datetime.now().date()
        final_date = date_referrer + timedelta(days=3)

        print("Final date: {}".format(final_date))
        print("Sending payment notifications via email")
        self.send_email(final_date)

    def handle(self, *args, **options):
        begin = time.time()
        print("Running...")
        self.run_command()
        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
