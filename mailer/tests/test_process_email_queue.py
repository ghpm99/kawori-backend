from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from mailer.models import EmailQueue, UserEmailPreference


class ProcessEmailQueueTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="worker_user", email="worker@test.com", password="testpass123")

    def _create_email(self, **kwargs):
        defaults = {
            "user": self.user,
            "to_email": "dest@test.com",
            "subject": "Test",
            "body_html": "<p>Hello</p>",
            "email_type": EmailQueue.TYPE_GENERIC,
            "status": EmailQueue.STATUS_PENDING,
            "scheduled_at": timezone.now(),
        }
        defaults.update(kwargs)
        return EmailQueue.objects.create(**defaults)

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_processes_pending_email(self, mock_send):
        email = self._create_email()
        out = StringIO()
        call_command("process_email_queue", "--once", stdout=out)
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SENT)
        self.assertIsNotNone(email.sent_at)
        mock_send.assert_called_once()

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_retries_failed_email(self, mock_send):
        email = self._create_email(status=EmailQueue.STATUS_FAILED, retry_count=1, max_retries=3)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SENT)

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_does_not_process_exhausted_retries(self, mock_send):
        email = self._create_email(status=EmailQueue.STATUS_FAILED, retry_count=3, max_retries=3)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_FAILED)
        mock_send.assert_not_called()

    @patch("mailer.management.commands.process_email_queue.Command.send_email", side_effect=Exception("SMTP error"))
    def test_marks_failed_on_send_error(self, mock_send):
        email = self._create_email()
        call_command("process_email_queue", "--once", stdout=StringIO(), stderr=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_FAILED)
        self.assertEqual(email.retry_count, 1)
        self.assertIn("SMTP error", email.last_error)

    @override_settings(MAILER_GLOBAL_ENABLED=False)
    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_skips_when_global_disabled(self, mock_send):
        email = self._create_email()
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SKIPPED)
        self.assertEqual(email.skip_reason, "envio global desabilitado")
        mock_send.assert_not_called()

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_skips_when_user_disabled_all(self, mock_send):
        UserEmailPreference.objects.create(user=self.user, allow_all_emails=False)
        email = self._create_email(category=EmailQueue.CATEGORY_NOTIFICATION)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SKIPPED)
        self.assertIn("desabilitou todos", email.skip_reason)
        mock_send.assert_not_called()

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_skips_notification_when_user_disabled(self, mock_send):
        UserEmailPreference.objects.create(user=self.user, allow_notification=False)
        email = self._create_email(category=EmailQueue.CATEGORY_NOTIFICATION)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SKIPPED)
        self.assertIn("notificacao", email.skip_reason)

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_sends_transactional_even_if_notification_disabled(self, mock_send):
        UserEmailPreference.objects.create(user=self.user, allow_notification=False)
        email = self._create_email(category=EmailQueue.CATEGORY_TRANSACTIONAL)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SENT)

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_sends_transactional_even_if_all_emails_disabled(self, mock_send):
        UserEmailPreference.objects.create(user=self.user, allow_all_emails=False)
        email = self._create_email(category=EmailQueue.CATEGORY_TRANSACTIONAL)
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_SENT)
        mock_send.assert_called_once()

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_does_not_process_future_scheduled(self, mock_send):
        from datetime import timedelta
        email = self._create_email(scheduled_at=timezone.now() + timedelta(hours=1))
        call_command("process_email_queue", "--once", stdout=StringIO())
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueue.STATUS_PENDING)
        mock_send.assert_not_called()

    @patch("mailer.management.commands.process_email_queue.Command.send_email")
    def test_processes_by_priority_order(self, mock_send):
        low = self._create_email(priority=EmailQueue.PRIORITY_LOW, subject="Low")
        high = self._create_email(priority=EmailQueue.PRIORITY_HIGH, subject="High")
        call_command("process_email_queue", "--once", "--batch-size=1", stdout=StringIO())
        high.refresh_from_db()
        low.refresh_from_db()
        self.assertEqual(high.status, EmailQueue.STATUS_SENT)
        self.assertEqual(low.status, EmailQueue.STATUS_PENDING)
