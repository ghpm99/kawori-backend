from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from mailer.models import EmailQueue
from mailer.utils import (
    enqueue_email,
    enqueue_email_verification,
    enqueue_password_reset,
    enqueue_payment_notification,
)


@override_settings(
    BASE_URL_FRONTEND="http://localhost:3000",
    EMAIL_HOST_USER="test@kawori.com",
)
class EnqueueEmailTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_enqueue_email_creates_record(self):
        email = enqueue_email(
            to_email="dest@test.com",
            subject="Test subject",
            template_name="password_reset_email.html",
            context={
                "user": self.user,
                "token": "abc",
                "reset_url": "http://test",
                "expiry_minutes": 30,
            },
            email_type=EmailQueue.TYPE_GENERIC,
            user=self.user,
        )
        self.assertEqual(email.status, EmailQueue.STATUS_PENDING)
        self.assertEqual(email.to_email, "dest@test.com")
        self.assertEqual(email.from_email, "test@kawori.com")
        self.assertIn("Test subject", email.subject)
        self.assertTrue(len(email.body_html) > 0)

    def test_enqueue_password_reset(self):
        email = enqueue_password_reset(self.user, "raw-token-123")
        self.assertEqual(email.email_type, EmailQueue.TYPE_PASSWORD_RESET)
        self.assertEqual(email.category, EmailQueue.CATEGORY_TRANSACTIONAL)
        self.assertEqual(email.priority, EmailQueue.PRIORITY_HIGH)
        self.assertEqual(email.to_email, "test@example.com")
        self.assertIn("Redefinição de senha", email.subject)

    def test_enqueue_email_verification(self):
        email = enqueue_email_verification(self.user, "verify-token-456")
        self.assertEqual(email.email_type, EmailQueue.TYPE_EMAIL_VERIFICATION)
        self.assertEqual(email.category, EmailQueue.CATEGORY_TRANSACTIONAL)
        self.assertEqual(email.priority, EmailQueue.PRIORITY_HIGH)
        self.assertIn("Verifique seu email", email.subject)

    def test_enqueue_payment_notification(self):
        payments = [
            {
                "id": 1,
                "type": "Boleto",
                "name": "Internet",
                "payment_date": "15/03/2026",
                "value": 100.0,
                "payment_url": "http://test/1",
            },
            {
                "id": 2,
                "type": "Cartão",
                "name": "Luz",
                "payment_date": "16/03/2026",
                "value": 50.0,
                "payment_url": "http://test/2",
            },
        ]
        from datetime import date

        final_date = date(2026, 3, 20)
        email = enqueue_payment_notification(self.user, payments, final_date)
        self.assertEqual(email.email_type, EmailQueue.TYPE_PAYMENT_NOTIFICATION)
        self.assertEqual(email.category, EmailQueue.CATEGORY_NOTIFICATION)
        self.assertEqual(email.priority, EmailQueue.PRIORITY_NORMAL)
        self.assertIn("20/03/2026", email.subject)

    @patch("mailer.utils.suggest_payment_notification_copy")
    def test_enqueue_payment_notification_uses_ai_subject_prefix(self, mocked_ai):
        mocked_ai.return_value = {
            "subject_prefix": "Alerta Financeiro",
            "intro": "Você possui pagamentos próximos.",
            "highlights": ["Internet em 15/03"],
        }
        payments = [
            {
                "id": 1,
                "type": "Boleto",
                "name": "Internet",
                "payment_date": "15/03/2026",
                "value": 100.0,
            }
        ]
        from datetime import date

        final_date = date(2026, 3, 20)

        email = enqueue_payment_notification(self.user, payments, final_date)

        self.assertTrue(email.subject.startswith("Alerta Financeiro"))
        self.assertIn("20/03/2026", email.subject)
