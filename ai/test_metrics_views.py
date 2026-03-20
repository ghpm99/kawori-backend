from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ai.models import AIExecutionEvent


class AIMetricsEndpointsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        admin_user = User.objects.create_user(username="aiadmin", email="aiadmin@test.com", password="123")
        admin_group, _ = Group.objects.get_or_create(name="admin")
        admin_group.user_set.add(admin_user)
        cls.user = admin_user

        now = timezone.now()
        AIExecutionEvent.objects.bulk_create(
            [
                AIExecutionEvent(
                    trace_id="t-1",
                    feature_name="payment_reconciliation",
                    task_type="structured_extraction",
                    provider="openai",
                    model="gpt-4o-mini",
                    attempts=1,
                    retry_count=0,
                    used_fallback=False,
                    latency_ms=800,
                    success=True,
                    prompt_tokens=120,
                    completion_tokens=40,
                    total_tokens=160,
                    cost_estimate=Decimal("0.002300"),
                    cache_status="miss",
                    user=admin_user,
                    created_at=now - timedelta(hours=6),
                ),
                AIExecutionEvent(
                    trace_id="t-2",
                    feature_name="audit_insights",
                    task_type="structured_extraction",
                    provider="anthropic",
                    model="claude-3-5-haiku-latest",
                    attempts=2,
                    retry_count=1,
                    used_fallback=True,
                    latency_ms=1200,
                    success=True,
                    prompt_tokens=300,
                    completion_tokens=90,
                    total_tokens=390,
                    cost_estimate=Decimal("0.005400"),
                    cache_status="hit",
                    user=admin_user,
                    created_at=now - timedelta(hours=3),
                ),
                AIExecutionEvent(
                    trace_id="t-3",
                    feature_name="communication_notifications",
                    task_type="structured_extraction",
                    provider="openai",
                    model="gpt-4o-mini",
                    attempts=1,
                    retry_count=0,
                    used_fallback=False,
                    latency_ms=500,
                    success=False,
                    error_message="timeout",
                    prompt_tokens=80,
                    completion_tokens=0,
                    total_tokens=80,
                    cost_estimate=Decimal("0.000700"),
                    cache_status="bypass",
                    user=admin_user,
                    created_at=now - timedelta(hours=1),
                ),
            ]
        )

        token = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "aiadmin", "password": "123"},
        )
        cls.cookies = token.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_metrics_overview_returns_expected_totals(self):
        response = self.client.get(reverse("ai_metrics_overview"))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]

        self.assertEqual(payload["totals"]["calls"], 3)
        self.assertEqual(payload["totals"]["success_calls"], 2)
        self.assertEqual(payload["totals"]["failed_calls"], 1)
        self.assertEqual(payload["totals"]["retry_attempts"], 1)
        self.assertGreater(payload["totals"]["cost_usd"], 0)

    def test_metrics_breakdown_by_feature(self):
        response = self.client.get(reverse("ai_metrics_breakdown"), data={"group_by": "feature_name"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]

        self.assertEqual(payload["group_by"], "feature_name")
        self.assertGreaterEqual(len(payload["rows"]), 3)

    def test_metrics_timeseries_day(self):
        response = self.client.get(reverse("ai_metrics_timeseries"), data={"interval": "day"})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]

        self.assertEqual(payload["interval"], "day")
        self.assertGreaterEqual(len(payload["rows"]), 1)
        self.assertIn("calls", payload["rows"][0])

    def test_metrics_events_pagination_and_filter(self):
        response = self.client.get(
            reverse("ai_metrics_events"),
            data={"page": 1, "page_size": 2, "provider": "openai"},
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]

        self.assertEqual(payload["page_size"], 2)
        self.assertGreaterEqual(payload["total"], 2)
        self.assertLessEqual(len(payload["rows"]), 2)
        for row in payload["rows"]:
            self.assertEqual(row["provider"], "openai")

    def test_metrics_invalid_group_returns_400(self):
        response = self.client.get(reverse("ai_metrics_breakdown"), data={"group_by": "invalid"})
        self.assertEqual(response.status_code, 400)
