import time
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from payment.models import Payment


class Command(BaseCommand):
    help = "Send payment email notifications"

    def send_email_to_user(self, user, final_date):
        user_payments = Payment.objects.filter(
            user=user,
            payment_date__lte=final_date,
            status=Payment.STATUS_OPEN,
            active=True,
        ).order_by("payment_date")

        if not user_payments.exists():
            return False

        payments = []
        total_value = 0

        for payment in user_payments:
            payment_value = float(payment.value)
            total_value += payment_value

            payments.append(
                {
                    "id": payment.id,
                    "type": Payment.TYPES[payment.type][1],
                    "name": payment.name,
                    "payment_date": payment.payment_date.strftime("%d/%m/%Y"),
                    "value": payment_value,
                    "payment_url": settings.BASE_URL_FRONTEND + "/admin/financial/payments/details/" + str(payment.id),
                }
            )

        html_content = render_to_string(
            "payment_email_template.html",
            {
                "payments": payments,
                "total_value": total_value,
                "final_date": final_date.strftime("%d/%m/%Y"),
            },
        )

        try:
            email = EmailMessage(
                subject=f'Notificação de Pagamentos - Vencimento até {final_date.strftime("%d/%m/%Y")}',
                body=html_content,
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email],
            )
            email.content_subtype = "html"
            email.send()
            print(f"Email sent successfully to {user.email} (user: {user.username})")
            return True
        except Exception as e:
            print(f"Error sending email to {user.email} (user: {user.username}): {str(e)}")
            return False

    def run_command(self):
        date_referrer = datetime.now().date()
        final_date = date_referrer + timedelta(days=3)

        print("Final date: {}".format(final_date))
        print("Sending payment notifications via email")

        users_with_payments = User.objects.filter(
            payment__payment_date__lte=final_date,
            payment__status=Payment.STATUS_OPEN,
            payment__active=True,
        ).distinct()

        if not users_with_payments.exists():
            print("No payments found to notify")
            return

        print(f"Found {users_with_payments.count()} user(s) with pending payments")

        sent_count = 0
        error_count = 0

        for user in users_with_payments:
            if not user.email:
                print(f"User {user.username} has no email address, skipping")
                continue

            if self.send_email_to_user(user, final_date):
                sent_count += 1
            else:
                error_count += 1

        print(f"Emails sent: {sent_count}, errors: {error_count}")

    def handle(self, *args, **options):
        begin = time.time()
        print("Running...")
        self.run_command()
        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
