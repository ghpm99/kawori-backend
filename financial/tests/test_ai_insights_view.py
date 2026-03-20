import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class FinancialAIInsightsViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        user = User.objects.create_superuser(
            username="insights", email="insights@test.com", password="123"
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)
        cls.user = user

        tag_food = Tag.objects.create(name="Alimentacao", color="#FF9900", user=user)
        tag_home = Tag.objects.create(name="Moradia", color="#3366FF", user=user)

        invoice = Invoice.objects.create(
            name="Fatura Insights",
            date=date(2026, 3, 1),
            installments=1,
            payment_date=date(2026, 3, 10),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("500.00"),
            value_closed=Decimal("500.00"),
            user=user,
        )
        invoice.tags.add(tag_food, tag_home)

        # Mes atual com aumento de gastos
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Delivery",
            description="iFood",
            date=date(2026, 3, 5),
            payment_date=date(2026, 3, 5),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("420.00"),
            status=Payment.STATUS_DONE,
            user=user,
            invoice=invoice,
            reference="",
        )

        # Base historica mais baixa
        for month in (12, 1, 2):
            Payment.objects.create(
                type=Payment.TYPE_DEBIT,
                name=f"Despesa {month}",
                description="Alimentacao",
                date=date(2025 if month == 12 else 2026, month, 10),
                payment_date=date(2025 if month == 12 else 2026, month, 10),
                installments=1,
                fixed=False,
                active=True,
                value=Decimal("160.00"),
                status=Payment.STATUS_DONE,
                user=user,
                invoice=invoice,
                reference="",
            )

        token_response = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "insights", "password": "123"},
        )
        cls.cookies = token_response.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_report_ai_insights_returns_priority_insights(self):
        response = self.client.post(
            reverse("financial_report_ai_insights"),
            data=json.dumps({"date_from": "2026-03-01", "date_to": "2026-03-31"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertIn("priority_insights", payload)
        self.assertGreaterEqual(len(payload["priority_insights"]), 1)

        first = payload["priority_insights"][0]
        for field in ("severity", "title", "metric", "context", "action", "confidence"):
            self.assertIn(field, first)
