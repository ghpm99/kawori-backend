from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from audit.ai_assist import build_audit_ai_insights


class AuditAIAssistTestCase(SimpleTestCase):
    def test_build_audit_ai_insights_includes_prompt_metadata(self):
        ai_response = SimpleNamespace(
            output={
                "summary": "Falhas concentradas em login.",
                "incident_clusters": ["login.failure"],
                "probable_root_causes": ["token expirado"],
                "recommended_actions": ["aumentar observabilidade"],
            },
            trace_id="trace-audit-1",
            provider="openai",
            model="gpt-4o-mini",
        )

        with patch("audit.ai_assist.safe_execute_ai_task", return_value=ai_response):
            result = build_audit_ai_insights(
                filters={"date_from": "2026-03-01"},
                summary={"total_events": 10, "failure_events": 4, "error_events": 0},
                interactions_by_day=[{"day": "2026-03-01", "count": 5}],
                by_action=[{"action": "login", "count": 4}],
                by_category=[{"category": "auth", "count": 4}],
                by_user=[{"username": "admin", "count": 20}],
                failures_by_action=[{"action": "login", "count": 4}],
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["summary"], "Falhas concentradas em login.")
        self.assertEqual(result["prompt_key"], "audit.insights.v1")
        self.assertEqual(result["prompt_source"], "file")
        self.assertEqual(result["prompt_version"], "v1")
        self.assertTrue(result["prompt_hash"])
