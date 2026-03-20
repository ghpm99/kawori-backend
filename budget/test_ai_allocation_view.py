import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from budget.models import Budget
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class BudgetAIAllocationViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        user = User.objects.create_superuser(
            username="budget-ai", email="budget-ai@test.com", password="123"
        )
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(user)
        cls.user = user

        tag_home = Tag.objects.create(name="Moradia", color="#123456", user=user)
        tag_transport = Tag.objects.create(
            name="Transporte", color="#654321", user=user
        )

        Budget.objects.create(
            user=user, tag=tag_home, allocation_percentage=Decimal("30.00")
        )
        Budget.objects.create(
            user=user, tag=tag_transport, allocation_percentage=Decimal("15.00")
        )

        invoice = Invoice.objects.create(
            name="Fatura Budget",
            date=date(2026, 3, 1),
            installments=1,
            payment_date=date(2026, 3, 10),
            fixed=False,
            value=Decimal("1000.00"),
            value_open=Decimal("400.00"),
            value_closed=Decimal("600.00"),
            user=user,
        )
        invoice.tags.add(tag_home, tag_transport)

        for month in range(10, 13):
            Payment.objects.create(
                type=Payment.TYPE_DEBIT,
                name=f"Despesa moradia {month}",
                description="Aluguel",
                date=date(2025, month, 5),
                payment_date=date(2025, month, 5),
                installments=1,
                fixed=False,
                active=True,
                value=Decimal("300.00"),
                status=Payment.STATUS_DONE,
                user=user,
                invoice=invoice,
                reference="",
            )

        token_response = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "budget-ai", "password": "123"},
        )
        cls.cookies = token_response.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def test_budget_ai_allocation_suggestions_returns_scenarios(self):
        response = self.client.get(
            reverse("budget_ai_allocation_suggestions"),
            data={"period": "03/2026"},
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)

        self.assertEqual(payload["recommended_scenario"], "base")
        self.assertEqual(len(payload["scenarios"]), 3)

        scenario_ids = {item["id"] for item in payload["scenarios"]}
        self.assertEqual(scenario_ids, {"conservative", "base", "aggressive"})
