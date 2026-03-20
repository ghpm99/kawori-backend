import time

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone

from mailer.models import EmailQueue, UserEmailPreference


class Command(BaseCommand):
    help = "Process pending emails from the queue"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Number of emails to process per cycle",
        )
        parser.add_argument(
            "--once", action="store_true", help="Process one batch and exit"
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=30,
            help="Seconds between cycles in continuous mode",
        )

    def check_user_preference(self, queued_email):
        if not queued_email.user:
            return None

        if queued_email.category == EmailQueue.CATEGORY_TRANSACTIONAL:
            return None

        try:
            pref = queued_email.user.email_preference
        except UserEmailPreference.DoesNotExist:
            return None

        if not pref.allow_all_emails:
            return "usuario desabilitou todos os emails"

        category = queued_email.category
        if category == EmailQueue.CATEGORY_NOTIFICATION and not pref.allow_notification:
            return "usuario desabilitou emails de notificacao"
        if category == EmailQueue.CATEGORY_PROMOTIONAL and not pref.allow_promotional:
            return "usuario desabilitou emails promocionais"

        return None

    def send_email(self, queued_email):
        email = EmailMessage(
            subject=queued_email.subject,
            body=queued_email.body_html,
            from_email=queued_email.from_email or settings.EMAIL_HOST_USER,
            to=[queued_email.to_email],
        )
        email.content_subtype = "html"
        email.send()

    def process_batch(self, batch_size):
        now = timezone.now()
        processed = 0

        email_ids = list(
            EmailQueue.objects.filter(
                status__in=[EmailQueue.STATUS_PENDING, EmailQueue.STATUS_FAILED],
                scheduled_at__lte=now,
                retry_count__lt=models.F("max_retries"),
            )
            .order_by("priority", "scheduled_at")
            .values_list("id", flat=True)[:batch_size]
        )

        for email_id in email_ids:
            self.process_single(email_id)
            processed += 1

        return processed

    def process_single(self, email_id):
        with transaction.atomic():
            try:
                queued_email = EmailQueue.objects.select_for_update(
                    skip_locked=True
                ).get(id=email_id)
            except EmailQueue.DoesNotExist:
                return

            if queued_email.status not in [
                EmailQueue.STATUS_PENDING,
                EmailQueue.STATUS_FAILED,
            ]:
                return

            if not getattr(settings, "MAILER_GLOBAL_ENABLED", True):
                queued_email.status = EmailQueue.STATUS_SKIPPED
                queued_email.skip_reason = "envio global desabilitado"
                queued_email.save(update_fields=["status", "skip_reason", "updated_at"])
                self.stdout.write(f"Skipped (global disabled): {queued_email.to_email}")
                return

            skip_reason = self.check_user_preference(queued_email)
            if skip_reason:
                queued_email.status = EmailQueue.STATUS_SKIPPED
                queued_email.skip_reason = skip_reason
                queued_email.save(update_fields=["status", "skip_reason", "updated_at"])
                self.stdout.write(f"Skipped ({skip_reason}): {queued_email.to_email}")
                return

            queued_email.status = EmailQueue.STATUS_SENDING
            queued_email.save(update_fields=["status", "updated_at"])

        try:
            self.send_email(queued_email)
            queued_email.status = EmailQueue.STATUS_SENT
            queued_email.sent_at = timezone.now()
            queued_email.save(update_fields=["status", "sent_at", "updated_at"])
            self.stdout.write(
                f"Sent: {queued_email.to_email} ({queued_email.email_type})"
            )

        except Exception as e:
            queued_email.status = EmailQueue.STATUS_FAILED
            queued_email.retry_count += 1
            queued_email.last_error = str(e)[:1000]
            queued_email.save(
                update_fields=["status", "retry_count", "last_error", "updated_at"]
            )
            self.stderr.write(f"Failed: {queued_email.to_email} - {e}")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        once = options["once"]
        interval = options["interval"]

        self.stdout.write(
            f"Email queue worker started (batch_size={batch_size}, once={once})"
        )

        while True:
            processed = self.process_batch(batch_size)
            if processed:
                self.stdout.write(f"Processed {processed} email(s)")

            if once:
                break

            time.sleep(interval)
