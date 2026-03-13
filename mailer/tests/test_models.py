from django.contrib.auth.models import User
from django.test import TestCase

from mailer.models import EmailQueue, UserEmailPreference


class EmailQueueModelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

    def test_create_email_queue(self):
        email = EmailQueue.objects.create(
            user=self.user,
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Hello</p>",
            email_type=EmailQueue.TYPE_GENERIC,
        )
        self.assertEqual(email.status, EmailQueue.STATUS_PENDING)
        self.assertEqual(email.priority, EmailQueue.PRIORITY_NORMAL)
        self.assertEqual(email.retry_count, 0)
        self.assertEqual(email.category, EmailQueue.CATEGORY_TRANSACTIONAL)

    def test_str_representation(self):
        email = EmailQueue.objects.create(
            to_email="test@example.com",
            subject="Test",
            body_html="<p>Hello</p>",
            email_type=EmailQueue.TYPE_PASSWORD_RESET,
        )
        self.assertIn("pending", str(email))
        self.assertIn("password_reset", str(email))
        self.assertIn("test@example.com", str(email))

    def test_default_ordering(self):
        high = EmailQueue.objects.create(
            to_email="a@test.com", subject="High", body_html="", priority=EmailQueue.PRIORITY_HIGH
        )
        low = EmailQueue.objects.create(
            to_email="b@test.com", subject="Low", body_html="", priority=EmailQueue.PRIORITY_LOW
        )
        normal = EmailQueue.objects.create(
            to_email="c@test.com", subject="Normal", body_html="", priority=EmailQueue.PRIORITY_NORMAL
        )
        emails = list(EmailQueue.objects.all())
        self.assertEqual(emails[0].id, high.id)
        self.assertEqual(emails[1].id, normal.id)
        self.assertEqual(emails[2].id, low.id)

    def test_user_nullable(self):
        email = EmailQueue.objects.create(
            to_email="nouser@test.com", subject="No user", body_html="<p>Test</p>"
        )
        self.assertIsNone(email.user)


class UserEmailPreferenceModelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="prefuser", email="pref@example.com", password="testpass123")

    def test_create_preference_defaults(self):
        pref = UserEmailPreference.objects.create(user=self.user)
        self.assertTrue(pref.allow_all_emails)
        self.assertTrue(pref.allow_notification)
        self.assertTrue(pref.allow_promotional)

    def test_str_representation(self):
        pref = UserEmailPreference.objects.create(user=self.user)
        self.assertIn("prefuser", str(pref))
