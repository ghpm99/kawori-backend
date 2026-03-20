import inspect
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from budget import views
from budget.models import Budget
from budget.services import DEFAULT_BUDGETS, create_default_budgets_for_user
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class BudgetViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="budget-reg", email="budget-reg@test.com", password="123"
        )

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None):
        payload = None if data is None else json.dumps(data)
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method(
                "/", data=payload, content_type="application/json"
            )

        target = inspect.unwrap(fn)
        return target(request, user=self.user)

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            status=kwargs.get("status", Invoice.STATUS_OPEN),
            type=kwargs.get("type", Invoice.Type.DEBIT),
            name=kwargs.get("name", "Inv"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            value_open=kwargs.get("value_open", Decimal("10.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
        )

    def _create_payment(self, **kwargs):
        return Payment.objects.create(
            status=kwargs.get("status", Payment.STATUS_OPEN),
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Pay"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", "ref"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            invoice=kwargs.get("invoice"),
            user=self.user,
        )

    def test_get_period_filter_with_valid_and_invalid_inputs(self):
        valid = views.get_period_filter({"period": "02/2026"})
        self.assertEqual(valid["start"].year, 2026)
        self.assertEqual(valid["start"].month, 2)
        self.assertEqual(valid["start"].day, 1)
        self.assertEqual(valid["end"].day, 28)

        with patch("budget.views.datetime") as mocked_datetime:
            mocked_now = date(2026, 3, 15)
            mocked_datetime.now.return_value.date.return_value = mocked_now
            invalid = views.get_period_filter({})

        self.assertEqual(invalid["start"], date(2026, 3, 1))
        self.assertEqual(invalid["end"], date(2026, 3, 15))

    def test_get_all_budgets_view_uses_real_credits_and_maps_debits_by_tag(self):
        fixed_tag = Tag.objects.create(
            name="Custos fixos", color="#1f77b4", user=self.user
        )
        entradas_tag = Tag.objects.create(
            name="Entradas", color="#000000", user=self.user
        )
        fixed_budget = Budget.objects.create(
            user=self.user, tag=fixed_tag, allocation_percentage=Decimal("40.00")
        )
        Budget.objects.create(
            user=self.user, tag=entradas_tag, allocation_percentage=Decimal("0.00")
        )

        invoice = self._create_invoice()
        invoice.tags.add(fixed_tag)

        self._create_payment(
            type=Payment.TYPE_CREDIT,
            value=Decimal("1000.00"),
            payment_date=date(2026, 1, 2),
            invoice=invoice,
        )
        self._create_payment(
            type=Payment.TYPE_DEBIT,
            value=Decimal("120.00"),
            payment_date=date(2026, 1, 3),
            invoice=invoice,
        )

        response = self._call(
            views.get_all_budgets_view, method="get", data={"period": "01/2026"}
        )
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], fixed_budget.id)
        self.assertEqual(payload[0]["name"], "Custos fixos")
        self.assertEqual(payload[0]["estimated_expense"], 400.0)
        self.assertEqual(payload[0]["actual_expense"], 120.0)

    def test_get_all_budgets_view_falls_back_to_predicted_fixed_total(self):
        comfort_tag = Tag.objects.create(
            name="Conforto", color="#ff7f0e", user=self.user
        )
        Budget.objects.create(
            user=self.user, tag=comfort_tag, allocation_percentage=Decimal("20.00")
        )

        invoice = self._create_invoice()
        invoice.tags.add(comfort_tag)

        self._create_payment(
            type=Payment.TYPE_CREDIT,
            fixed=True,
            active=True,
            name="Salary",
            value=Decimal("500.00"),
            payment_date=date(2026, 2, 5),
            invoice=invoice,
        )
        self._create_payment(
            type=Payment.TYPE_CREDIT,
            fixed=True,
            active=True,
            name="Salary",
            value=Decimal("750.00"),
            payment_date=date(2026, 3, 5),
            invoice=invoice,
        )
        self._create_payment(
            type=Payment.TYPE_DEBIT,
            fixed=False,
            active=True,
            name="Spend",
            value=Decimal("50.00"),
            payment_date=date(2026, 1, 10),
            invoice=invoice,
        )

        with patch("budget.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 3, 20)
            mocked_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
            response = self._call(
                views.get_all_budgets_view, method="get", data={"period": "01/2026"}
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["estimated_expense"], 150.0)
        self.assertEqual(payload[0]["actual_expense"], 50.0)

    def test_save_budget_view_updates_only_existing_rows(self):
        tag = Tag.objects.create(name="Metas", color="#2ca02c", user=self.user)
        budget = Budget.objects.create(
            user=self.user, tag=tag, allocation_percentage=Decimal("5.00")
        )

        response = self._call(
            views.save_budget_view,
            method="post",
            data={
                "data": [
                    {"id": budget.id, "allocation_percentage": "12.50"},
                    {"id": 999999, "allocation_percentage": "77.00"},
                ]
            },
        )
        self.assertEqual(response.status_code, 200)

        budget.refresh_from_db()
        self.assertEqual(budget.allocation_percentage, Decimal("12.50"))

    def test_reset_budget_allocation_view_restores_defaults_by_tag_name_case_insensitive(
        self,
    ):
        tag = Tag.objects.create(name="conforto", color="#ff7f0e", user=self.user)
        budget = Budget.objects.create(
            user=self.user, tag=tag, allocation_percentage=Decimal("99.00")
        )

        response = self._call(views.reset_budget_allocation_view, method="get", data={})
        self.assertEqual(response.status_code, 200)

        budget.refresh_from_db()
        self.assertEqual(budget.allocation_percentage, Decimal("20.00"))


class BudgetServicesRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="budget-svc", email="budget-svc@test.com", password="123"
        )

    def test_create_default_budgets_for_user_creates_all_defaults(self):
        create_default_budgets_for_user(self.user)

        self.assertEqual(
            Budget.objects.filter(user=self.user).count(), len(DEFAULT_BUDGETS)
        )
        self.assertEqual(
            Tag.objects.filter(user=self.user).count(), len(DEFAULT_BUDGETS)
        )

    def test_create_default_budgets_for_user_updates_existing_tag_color_and_budget_percentage(
        self,
    ):
        tag = Tag.objects.create(name="  conforto  ", color="#000000", user=self.user)
        budget = Budget.objects.create(
            user=self.user, tag=tag, allocation_percentage=Decimal("99.99")
        )

        create_default_budgets_for_user(self.user)

        tag.refresh_from_db()
        budget.refresh_from_db()
        self.assertEqual(tag.color, "#ff7f0e")
        self.assertEqual(budget.allocation_percentage, Decimal("20.00"))

    def test_create_default_budgets_for_user_handles_exception(self):
        with patch(
            "budget.services.Tag.objects.annotate", side_effect=Exception("boom")
        ), patch("builtins.print") as mocked_print:
            create_default_budgets_for_user(self.user)

        mocked_print.assert_called_once()
