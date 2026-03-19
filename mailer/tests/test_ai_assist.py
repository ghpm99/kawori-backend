from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from mailer.ai_assist import suggest_payment_notification_copy


class MailerAIAssistTestCase(SimpleTestCase):
    def test_suggest_payment_notification_copy_includes_prompt_metadata(self):
        ai_response = SimpleNamespace(
            output={
                "subject_prefix": "Alerta de Pagamentos",
                "intro": "Você possui pagamentos próximos do vencimento.",
                "highlights": ["Internet em 20/03"],
            },
            trace_id="trace-mailer-1",
            provider="openai",
            model="gpt-4o-mini",
        )

        with patch("mailer.ai_assist.safe_execute_ai_task", return_value=ai_response):
            result = suggest_payment_notification_copy(
                user=SimpleNamespace(username="financeiro"),
                payments=[{"name": "Internet", "value": 100.0, "payment_date": "20/03/2026", "type": "Boleto"}],
                final_date=date(2026, 3, 20),
                channel="email",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["subject_prefix"], "Alerta de Pagamentos")
        self.assertEqual(result["prompt_key"], "mailer.communication_notifications.v1")
        self.assertEqual(result["prompt_source"], "file")
        self.assertEqual(result["prompt_version"], "v1")
        self.assertTrue(result["prompt_hash"])
