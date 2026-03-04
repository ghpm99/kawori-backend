import inspect
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from contract.models import Contract
from contract import views
from invoice.models import Invoice
from tag.models import Tag


class ContractViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="contract-reg", email="contract-reg@test.com", password="123")
        cls.other_user = User.objects.create_superuser(
            username="contract-reg-other", email="contract-reg-other@test.com", password="123"
        )

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None, *, id=None):
        payload = None if data is None else json.dumps(data)
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method("/", data=payload, content_type="application/json")

        target = inspect.unwrap(fn)
        if id is None:
            return target(request, user=self.user)
        return target(request, id=id, user=self.user)

    def _create_contract(self, **kwargs):
        return Contract.objects.create(
            name=kwargs.get("name", "Contract"),
            value=kwargs.get("value", Decimal("0.00")),
            value_open=kwargs.get("value_open", Decimal("0.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=kwargs.get("user", self.user),
        )

    def _create_invoice(self, contract=None, **kwargs):
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
            value_open=kwargs.get("value_open", Decimal("100.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            contract=contract,
            user=kwargs.get("user", self.user),
        )

    def test_get_all_contract_view_with_and_without_filter(self):
        contract_a = self._create_contract(name="A", value=Decimal("10.00"))
        self._create_contract(name="B", value=Decimal("20.00"))

        all_response = self._call(views.get_all_contract_view, method="get", data={"page": 1, "page_size": 10})
        self.assertEqual(all_response.status_code, 200)
        all_payload = json.loads(all_response.content)["data"]["data"]
        self.assertEqual(len(all_payload), 2)

        filtered_response = self._call(
            views.get_all_contract_view,
            method="get",
            data={"id": contract_a.id, "page": 1, "page_size": 10},
        )
        filtered_payload = json.loads(filtered_response.content)["data"]["data"]
        self.assertEqual(len(filtered_payload), 1)
        self.assertEqual(filtered_payload[0]["id"], contract_a.id)

    def test_save_new_contract_view(self):
        response = self._call(views.save_new_contract_view, method="post", data={"name": "New C"})
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content)["data"]
        self.assertTrue(Contract.objects.filter(id=payload["id"], name="New C", user=self.user).exists())

    def test_detail_contract_view_success_and_not_found(self):
        contract = self._create_contract(name="Detail C")

        success = self._call(views.detail_contract_view, id=contract.id)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(json.loads(success.content)["data"]["name"], "Detail C")

        not_found = self._call(views.detail_contract_view, id=99999)
        self.assertEqual(not_found.status_code, 404)

    def test_detail_contract_view_does_not_expose_other_user_contract(self):
        other_contract = self._create_contract(name="Other Tenant", user=self.other_user)
        response = self._call(views.detail_contract_view, id=other_contract.id)
        self.assertEqual(response.status_code, 404)

    def test_detail_contract_invoices_view_returns_active_contract_invoices_with_tags(self):
        contract = self._create_contract(name="Invoices C")
        active_invoice = self._create_invoice(contract=contract, name="Active", active=True, value=Decimal("30.00"))
        self._create_invoice(contract=contract, name="Inactive", active=False, value=Decimal("90.00"))
        other_contract = self._create_contract(name="Other")
        self._create_invoice(contract=other_contract, name="Other contract", active=True)

        tag = Tag.objects.create(name="TagC", color="#111111", user=self.user)
        active_invoice.tags.add(tag)

        response = self._call(
            views.detail_contract_invoices_view,
            id=contract.id,
            method="get",
            data={"page": 1, "page_size": 10},
        )
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.content)["data"]["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Active")
        self.assertEqual(payload[0]["tags"][0]["name"], "TagC")

    def test_include_new_invoice_view_not_found_and_success(self):
        not_found = self._call(views.include_new_invoice_view, method="post", id=99999, data={"name": "x"})
        self.assertEqual(not_found.status_code, 404)

        contract = self._create_contract(name="Target", value=Decimal("10.00"), value_open=Decimal("10.00"))
        tag = Tag.objects.create(name="NewTag", color="#222222", user=self.user)

        with patch("contract.views.generate_payments") as mocked_generate:
            success = self._call(
                views.include_new_invoice_view,
                method="post",
                id=contract.id,
                data={
                    "status": Invoice.STATUS_OPEN,
                    "type": Invoice.Type.DEBIT,
                    "name": "New invoice",
                    "date": "2026-01-01",
                    "installments": 1,
                    "payment_date": "2026-01-02",
                    "fixed": False,
                    "active": True,
                    "value": 30,
                    "tags": [tag.id],
                },
            )

        self.assertEqual(success.status_code, 200)
        created = Invoice.objects.get(name="New invoice", contract=contract, user=self.user)
        self.assertEqual(created.tags.count(), 1)
        mocked_generate.assert_called_once_with(created)

        contract.refresh_from_db()
        self.assertEqual(contract.value, Decimal("40.00"))
        self.assertEqual(contract.value_open, Decimal("40.00"))

    def test_include_new_invoice_view_rejects_tag_from_other_user(self):
        contract = self._create_contract(name="Target", value=Decimal("10.00"), value_open=Decimal("10.00"))
        foreign_tag = Tag.objects.create(name="Foreign", color="#333333", user=self.other_user)

        response = self._call(
            views.include_new_invoice_view,
            method="post",
            id=contract.id,
            data={
                "status": Invoice.STATUS_OPEN,
                "type": Invoice.Type.DEBIT,
                "name": "New invoice invalid",
                "date": "2026-01-01",
                "installments": 1,
                "payment_date": "2026-01-02",
                "fixed": False,
                "active": True,
                "value": 30,
                "tags": [foreign_tag.id],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Invoice.objects.filter(name="New invoice invalid", user=self.user).exists())

    def test_merge_contract_view_not_found_and_success(self):
        not_found = self._call(views.merge_contract_view, method="post", id=99999, data={"contracts": []})
        self.assertEqual(not_found.status_code, 404)

        target = self._create_contract(name="Target")
        source = self._create_contract(name="Source")
        source_two = self._create_contract(name="Source 2")
        moved_one = self._create_invoice(contract=source, name="Move 1")
        moved_two = self._create_invoice(contract=source_two, name="Move 2")

        with patch("contract.views.update_contract_value") as mocked_update:
            success = self._call(
                views.merge_contract_view,
                method="post",
                id=target.id,
                data={"contracts": [source.id, source_two.id]},
            )

        self.assertEqual(success.status_code, 200)
        moved_one.refresh_from_db()
        moved_two.refresh_from_db()
        self.assertEqual(moved_one.contract_id, target.id)
        self.assertEqual(moved_two.contract_id, target.id)
        self.assertFalse(Contract.objects.filter(id=source.id).exists())
        self.assertFalse(Contract.objects.filter(id=source_two.id).exists())
        mocked_update.assert_called_once_with(target)

    def test_merge_contract_view_does_not_delete_contract_from_other_user(self):
        target = self._create_contract(name="Target")
        foreign_contract = self._create_contract(name="Foreign", user=self.other_user)

        response = self._call(
            views.merge_contract_view,
            method="post",
            id=target.id,
            data={"contracts": [foreign_contract.id]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contract.objects.filter(id=foreign_contract.id, user=self.other_user).exists())

    def test_update_all_contracts_value_calls_service_for_each_contract(self):
        contract_a = self._create_contract(name="A")
        contract_b = self._create_contract(name="B")
        foreign_contract = self._create_contract(name="Foreign", user=self.other_user)

        with patch("contract.views.update_contract_value") as mocked_update:
            response = self._call(views.update_all_contracts_value, method="post", data={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_update.call_count, 2)
        called_with = {call.args[0].id for call in mocked_update.call_args_list}
        self.assertEqual(called_with, {contract_a.id, contract_b.id})
        self.assertNotIn(foreign_contract.id, called_with)


class ContractModelsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="contract-models", email="contract-models@test.com", password="123")

    def test_set_value_updates_total_and_open(self):
        contract = Contract.objects.create(name="C", value=Decimal("10.00"), value_open=Decimal("10.00"), user=self.user)

        contract.set_value(Decimal("5.00"))
        contract.refresh_from_db()

        self.assertEqual(contract.value, Decimal("15.00"))
        self.assertEqual(contract.value_open, Decimal("15.00"))

    def test_close_value_updates_open_and_closed(self):
        contract = Contract.objects.create(
            name="C2",
            value=Decimal("20.00"),
            value_open=Decimal("20.00"),
            value_closed=Decimal("0.00"),
            user=self.user,
        )

        contract.close_value(Decimal("7.50"))
        contract.refresh_from_db()

        self.assertEqual(contract.value_open, Decimal("12.50"))
        self.assertEqual(contract.value_closed, Decimal("7.50"))
