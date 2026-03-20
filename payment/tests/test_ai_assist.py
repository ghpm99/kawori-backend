from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from payment.ai_assist import suggest_import_resolution, suggest_payment_normalization
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
        self.assertEqual(suggestion["prompt_key"], "payment.reconciliation.v1")
        self.assertEqual(suggestion["prompt_source"], "file")
        self.assertEqual(suggestion["prompt_version"], "v1")
        self.assertTrue(suggestion["prompt_hash"])

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

    def test_suggest_payment_normalization_includes_prompt_metadata(self):
        main_payment = SimpleNamespace(
            raw_name="Mercado XPTO",
            raw_description="Compras do mês",
            reference="ref-123",
            raw_date=date(2026, 1, 10),
            raw_payment_date=date(2026, 1, 10),
            raw_value=100.0,
        )
        payments_to_process = [
            SimpleNamespace(
                raw_name="Mercado XPTO", raw_description="Compra 1", raw_value=70.0
            ),
            SimpleNamespace(
                raw_name="Mercado XPTO", raw_description="Compra 2", raw_value=30.0
            ),
        ]

        ai_response = SimpleNamespace(
            output={
                "normalized_name": "Mercado XPTO",
                "normalized_description": "Compras variadas",
                "installments_total": 2,
                "tag_names": ["Alimentação", "Mercado"],
                "confidence": 0.95,
                "reason": "Padrão textual consistente.",
            },
            trace_id="trace-2",
            provider="openai",
            model="gpt-4o-mini",
        )

        with patch("payment.ai_assist.safe_execute_ai_task", return_value=ai_response):
            normalized = suggest_payment_normalization(
                main_payment, payments_to_process
            )

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["normalized_name"], "Mercado XPTO")
        self.assertEqual(normalized["installments_total"], 2)
        self.assertEqual(normalized["prompt_key"], "payment.normalization.v1")
        self.assertEqual(normalized["prompt_source"], "file")
        self.assertEqual(normalized["prompt_version"], "v1")
        self.assertTrue(normalized["prompt_hash"])
