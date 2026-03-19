from __future__ import annotations

from datetime import timedelta

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ai.models import PromptOverride
from ai.prompt_service import (
    PromptRenderError,
    PromptService,
    build_ai_request_from_prompt,
    render_prompt_template,
    reset_prompt_service_cache,
)


class PromptServiceFileResolutionTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        reset_prompt_service_cache()

    def tearDown(self):
        reset_prompt_service_cache()
        super().tearDown()

    def test_resolves_from_file_when_no_override(self):
        resolution = PromptService().resolve("payment.reconciliation.v1", environment="development")

        self.assertEqual(resolution.key, "payment.reconciliation.v1")
        self.assertEqual(resolution.source, "file")
        self.assertEqual(resolution.version, "v1")
        self.assertEqual(resolution.task_type, "structured_extraction")
        self.assertTrue(resolution.content_hash)

    def test_strict_render_fails_when_variable_is_missing(self):
        with self.assertRaises(PromptRenderError):
            render_prompt_template("Olá {{user.name}} - {{missing}}", {"user": {"name": "Kawori"}}, strict=True)

    def test_build_ai_request_uses_registry_schema_for_each_feature(self):
        cases = {
            "payment.reconciliation.v1": {"import_strategy", "matched_payment_id", "merge_group", "confidence", "reason"},
            "mailer.communication_notifications.v1": {"subject_prefix", "intro", "highlights"},
            "audit.insights.v1": {"summary", "incident_clusters", "probable_root_causes", "recommended_actions"},
            "release.compliance.v1": {
                "release_compliance_notes",
                "oneoff_required",
                "oneoff_reason",
                "suggested_regression_tests",
            },
        }

        for prompt_key, expected_schema_keys in cases.items():
            built = build_ai_request_from_prompt(prompt_key=prompt_key, payload={"ok": True}, feature_name="unit_test")
            metadata = built.task_request.metadata

            self.assertEqual(built.task_request.task_type, "structured_extraction")
            self.assertEqual(set(metadata["schema"].keys()), expected_schema_keys)
            self.assertEqual(metadata["prompt_key"], prompt_key)
            self.assertIn("prompt_hash", metadata)


@override_settings(AI_PROMPT_DB_OVERRIDE_ENABLED=True, AI_PROMPT_ENVIRONMENT="development")
class PromptServiceOverrideTestCase(TestCase):
    def setUp(self):
        super().setUp()
        reset_prompt_service_cache()

    def tearDown(self):
        reset_prompt_service_cache()
        super().tearDown()

    def test_resolves_from_db_when_active_override_exists(self):
        now = timezone.now()
        PromptOverride.objects.create(
            key="payment.reconciliation.v1",
            environment="development",
            content="Instrução customizada de override.",
            task_type="structured_extraction",
            schema_json={"import_strategy": "string"},
            temperature=0.3,
            max_tokens=111,
            is_active=True,
            version="v2",
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(days=1),
            change_reason="Teste de override ativo.",
        )

        resolution = PromptService().resolve("payment.reconciliation.v1", environment="development")

        self.assertEqual(resolution.source, "db")
        self.assertEqual(resolution.version, "v2")
        self.assertEqual(resolution.temperature, 0.3)
        self.assertEqual(resolution.max_tokens, 111)
        self.assertEqual(resolution.content, "Instrução customizada de override.")

    def test_falls_back_to_file_when_override_is_expired(self):
        now = timezone.now()
        PromptOverride.objects.create(
            key="payment.reconciliation.v1",
            environment="development",
            content="Instrução expirada.",
            task_type="structured_extraction",
            schema_json={"import_strategy": "string"},
            temperature=0.2,
            max_tokens=120,
            is_active=True,
            version="v3",
            valid_from=now - timedelta(days=2),
            valid_until=now - timedelta(days=1),
            change_reason="Teste de expiração.",
        )

        resolution = PromptService().resolve("payment.reconciliation.v1", environment="development")

        self.assertEqual(resolution.source, "file")
        self.assertEqual(resolution.version, "v1")

    def test_falls_back_to_file_when_override_is_invalid(self):
        PromptOverride.objects.create(
            key="payment.reconciliation.v1",
            environment="development",
            content="Instrução inválida.",
            task_type="invalid_task",
            schema_json={"import_strategy": "string"},
            temperature=0.2,
            max_tokens=120,
            is_active=True,
            version="v4",
            change_reason="Teste de override inválido.",
        )

        resolution = PromptService().resolve("payment.reconciliation.v1", environment="development")

        self.assertEqual(resolution.source, "file")
        self.assertEqual(resolution.version, "v1")
