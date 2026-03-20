import inspect
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from budget.models import Budget
from invoice.models import Invoice
from tag import views
from tag.models import Tag


class TagViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="tag-reg", email="tag-reg@test.com", password="123"
        )

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None, *, id=None):
        payload = None if data is None else json.dumps(data)
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method(
                "/", data=payload, content_type="application/json"
            )

        target = inspect.unwrap(fn)
        if id is None:
            return target(request, user=self.user)
        return target(request, id=id, user=self.user)

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
            value=kwargs.get("value", Decimal("100.00")),
            value_open=kwargs.get("value_open", Decimal("60.00")),
            value_closed=kwargs.get("value_closed", Decimal("40.00")),
            user=self.user,
        )

    def test_get_all_tag_view_returns_aggregates_and_budget_flag(self):
        regular_tag = Tag.objects.create(
            name="Mercado", color="#111111", user=self.user
        )
        budget_tag = Tag.objects.create(
            name="Conforto", color="#222222", user=self.user
        )
        Budget.objects.create(
            user=self.user, tag=budget_tag, allocation_percentage=Decimal("20.00")
        )

        active_invoice = self._create_invoice(
            name="Ativa",
            active=True,
            value=Decimal("90.00"),
            value_open=Decimal("30.00"),
            value_closed=Decimal("60.00"),
        )
        inactive_invoice = self._create_invoice(
            name="Inativa",
            active=False,
            value=Decimal("999.00"),
            value_open=Decimal("999.00"),
            value_closed=Decimal("0.00"),
        )
        active_invoice.tags.add(regular_tag, budget_tag)
        inactive_invoice.tags.add(regular_tag)

        response = self._call(
            views.get_all_tag_view, method="get", data={"name__icontains": "er"}
        )
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Mercado")
        self.assertEqual(payload[0]["total_payments"], 1)
        self.assertEqual(float(payload[0]["total_value"]), 90.0)
        self.assertEqual(float(payload[0]["total_open"]), 30.0)
        self.assertEqual(float(payload[0]["total_closed"]), 60.0)
        self.assertFalse(payload[0]["is_budget"])

        all_response = self._call(views.get_all_tag_view, method="get", data={})
        all_payload = json.loads(all_response.content)["data"]
        budget_item = next(item for item in all_payload if item["id"] == budget_tag.id)
        self.assertEqual(budget_item["name"], "# Conforto")
        self.assertTrue(budget_item["is_budget"])

    def test_detail_tag_view_success_and_not_found(self):
        tag = Tag.objects.create(name="Detail", color="#abcdef", user=self.user)

        success = self._call(views.detail_tag_view, id=tag.id)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(json.loads(success.content)["data"]["name"], "Detail")

        not_found = self._call(views.detail_tag_view, id=99999)
        self.assertEqual(not_found.status_code, 404)

    def test_include_new_tag_view_validations_and_success(self):
        Tag.objects.create(name="Existing", color="#101010", user=self.user)

        duplicate = self._call(
            views.include_new_tag_view,
            method="post",
            data={"name": "Existing", "color": "#202020"},
        )
        self.assertEqual(duplicate.status_code, 404)

        missing_name = self._call(
            views.include_new_tag_view,
            method="post",
            data={"name": " ", "color": "#202020"},
        )
        self.assertEqual(missing_name.status_code, 400)

        hash_name = self._call(
            views.include_new_tag_view,
            method="post",
            data={"name": "#invalid", "color": "#202020"},
        )
        self.assertEqual(hash_name.status_code, 400)

        missing_color = self._call(
            views.include_new_tag_view, method="post", data={"name": "Nova"}
        )
        self.assertEqual(missing_color.status_code, 400)

        success = self._call(
            views.include_new_tag_view,
            method="post",
            data={"name": "Nova", "color": "#333333"},
        )
        self.assertEqual(success.status_code, 200)
        self.assertTrue(Tag.objects.filter(name="Nova", user=self.user).exists())

    def test_save_tag_view_success_and_not_found(self):
        tag = Tag.objects.create(name="Old", color="#111111", user=self.user)

        success = self._call(
            views.save_tag_view,
            method="post",
            id=tag.id,
            data={"name": "New", "color": "#222222"},
        )
        self.assertEqual(success.status_code, 200)
        tag.refresh_from_db()
        self.assertEqual(tag.name, "New")
        self.assertEqual(tag.color, "#222222")

        not_found = self._call(
            views.save_tag_view,
            method="post",
            id=99999,
            data={"name": "X", "color": "#000000"},
        )
        self.assertEqual(not_found.status_code, 404)
