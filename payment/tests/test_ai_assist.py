from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from payment.ai_assist import suggest_import_resolution
from payment.utils import PaymentDetail


class PaymentAIAssistTestCase(SimpleTestCase):
    def _build_detail(self):
        return PaymentDetail(
            id=None,
            status=0,
            type=1,
            name="Mercado XPTO",
            description="Compra no mercado",
            reference="ref-1",
            date=date(2026, 1, 10),
            installments=1,
            payment_date=date(2026, 1, 10),
            fixed=False,
            active=True,
            value=100,
            invoice_id=None,
            user_id=10,
        )

    def test_suggest_import_resolution_returns_sanitized_output(self):
        parsed_transaction = SimpleNamespace(
            mapped_data=self._build_detail(),
            matched_payment=None,
            possibly_matched_payment_list=[
                {
                    "payment": SimpleNamespace(
                        id=12,
                        name="Mercado XPTO",
                        description="Compra no mercado",
                        date=date(2026, 1, 10),
                        payment_date=date(2026, 1, 10),
                        installments=1,
                        value=100,
                    ),
                    "score": 0.89,
                }
            ],
        )
        ai_response = SimpleNamespace(
            output={
                "import_strategy": "merge",
                "matched_payment_id": 12,
                "merge_group": "grp-2026-01",
                "confidence": 0.91,
                "reason": "Descrição e valor compatíveis.",
            },
            trace_id="trace-1",
            provider="openai",
            model="gpt-4o-mini",
        )

        with patch("payment.ai_assist.safe_execute_ai_task", return_value=ai_response):
            suggestion = suggest_import_resolution(
                user=SimpleNamespace(id=10),
                parsed_transaction=parsed_transaction,
                import_type="transactions",
            )

        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["import_strategy"], "merge")
        self.assertEqual(suggestion["matched_payment_id"], 12)
        self.assertEqual(suggestion["merge_group"], "grp-2026-01")
        self.assertEqual(suggestion["provider"], "openai")

    def test_suggest_import_resolution_returns_none_when_already_matched(self):
        parsed_transaction = SimpleNamespace(
            mapped_data=self._build_detail(),
            matched_payment=SimpleNamespace(id=1),
            possibly_matched_payment_list=[],
        )

        with patch("payment.ai_assist.safe_execute_ai_task") as mocked_ai:
            suggestion = suggest_import_resolution(
                user=SimpleNamespace(id=10),
                parsed_transaction=parsed_transaction,
                import_type="transactions",
            )

        self.assertIsNone(suggestion)
        mocked_ai.assert_not_called()
