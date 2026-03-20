from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mailer.models import EmailQueue


class Command(BaseCommand):
    help = "Delete old processed emails from the queue"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30, help="Delete emails older than N days"
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)

        deleted_count, _ = EmailQueue.objects.filter(
            status__in=[
                EmailQueue.STATUS_SENT,
                EmailQueue.STATUS_CANCELLED,
                EmailQueue.STATUS_SKIPPED,
            ],
            updated_at__lt=cutoff,
        ).delete()

        self.stdout.write(f"Deleted {deleted_count} email(s) older than {days} days")
