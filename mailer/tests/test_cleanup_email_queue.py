from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from mailer.models import EmailQueue


class CleanupEmailQueueTestCase(TestCase):
    def _create_email(self, status, days_old=0):
        email = EmailQueue.objects.create(
            to_email="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            status=status,
        )
        if days_old:
            old_date = timezone.now() - timedelta(days=days_old)
            EmailQueue.objects.filter(id=email.id).update(updated_at=old_date)
        return email

    def test_deletes_old_sent_emails(self):
        old_sent = self._create_email(EmailQueue.STATUS_SENT, days_old=31)
        recent_sent = self._create_email(EmailQueue.STATUS_SENT, days_old=5)
        call_command("cleanup_email_queue", "--days=30", stdout=StringIO())
        self.assertFalse(EmailQueue.objects.filter(id=old_sent.id).exists())
        self.assertTrue(EmailQueue.objects.filter(id=recent_sent.id).exists())

    def test_deletes_old_skipped_emails(self):
        old_skipped = self._create_email(EmailQueue.STATUS_SKIPPED, days_old=31)
        call_command("cleanup_email_queue", "--days=30", stdout=StringIO())
        self.assertFalse(EmailQueue.objects.filter(id=old_skipped.id).exists())

    def test_does_not_delete_pending_or_failed(self):
        old_pending = self._create_email(EmailQueue.STATUS_PENDING, days_old=60)
        old_failed = self._create_email(EmailQueue.STATUS_FAILED, days_old=60)
        call_command("cleanup_email_queue", "--days=30", stdout=StringIO())
        self.assertTrue(EmailQueue.objects.filter(id=old_pending.id).exists())
        self.assertTrue(EmailQueue.objects.filter(id=old_failed.id).exists())

    def test_custom_days_parameter(self):
        email = self._create_email(EmailQueue.STATUS_SENT, days_old=8)
        call_command("cleanup_email_queue", "--days=7", stdout=StringIO())
        self.assertFalse(EmailQueue.objects.filter(id=email.id).exists())
