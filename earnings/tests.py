import inspect
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from contract.models import Contract
from earnings import views
from invoice.models import Invoice
from payment.models import Payment


class EarningsViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="earnings-reg", email="earnings-reg@test.com", password="123")

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None):
        request_factory_method = getattr(self.rf, method.lower())
        request = request_factory_method("/", data=data or {})
        return inspect.unwrap(fn)(request, user=self.user)

    def _create_contract(self, **kwargs):
        return Contract.objects.create(
            name=kwargs.get("name", "Salary Contract"),
            value=kwargs.get("value", Decimal("0.00")),
            value_open=kwargs.get("value_open", Decimal("0.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
        )

    def _create_invoice(self, contract, **kwargs):
        return Invoice.objects.create(
            status=kwargs.get("status", Invoice.STATUS_OPEN),
            type=kwargs.get("type", Invoice.Type.CREDIT),
            name=kwargs.get("name", "Income Invoice"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("1000.00")),
            value_open=kwargs.get("value_open", Decimal("1000.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            contract=contract,
            user=self.user,
        )

    def _create_payment(self, invoice, **kwargs):
        return Payment.objects.create(
            status=kwargs.get("status", Payment.STATUS_OPEN),
            type=kwargs.get("type", Payment.TYPE_CREDIT),
            name=kwargs.get("name", "Salary"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", "ref"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", True),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("1000.00")),
            invoice=invoice,
            user=self.user,
        )

    def test_get_status_filter_helper(self):
        self.assertIsNone(views.get_status_filter("all"))
        self.assertEqual(views.get_status_filter("open"), Payment.STATUS_OPEN)
        self.assertEqual(views.get_status_filter("0"), Payment.STATUS_OPEN)
        self.assertEqual(views.get_status_filter("done"), Payment.STATUS_DONE)
        self.assertEqual(views.get_status_filter("1"), Payment.STATUS_DONE)
        self.assertIsNone(views.get_status_filter("x"))

    def test_get_all_view_with_filters_and_payload_contract_fields(self):
        contract = self._create_contract(name="Main Job")
        invoice = self._create_invoice(contract=contract, payment_date=date(2026, 1, 10))
        self._create_payment(
            invoice=invoice,
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_CREDIT,
            name="Salary January",
            payment_date=date(2026, 1, 10),
            fixed=True,
            active=True,
            installments=1,
            value=Decimal("2500.00"),
        )
        self._create_payment(
            invoice=invoice,
            status=Payment.STATUS_DONE,
            type=Payment.TYPE_DEBIT,
            name="Should be filtered out",
            payment_date=date(2026, 1, 11),
            fixed=False,
            active=False,
            value=Decimal("100.00"),
        )

        response = self._call(
            views.get_all_view,
            data={
                "status": "open",
                "type": str(Payment.TYPE_CREDIT),
                "name__icontains": "Salary",
                "date__gte": "2026-01-01",
                "date__lte": "2026-01-31",
                "installments": "1",
                "payment_date__gte": "2026-01-01",
                "payment_date__lte": "2026-01-31",
                "fixed": "true",
                "active": "true",
                "contract": "Main",
                "page": 1,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], "Salary January")
        self.assertEqual(payload[0]["contract_name"], "Main Job")
        self.assertEqual(payload[0]["contract_id"], contract.id)
