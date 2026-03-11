import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from invoice.models import Invoice
from payment.models import Payment


class GetPaymentsMonthTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = User.objects.create_superuser(username="test", email="test@test.com", password="123")
        financial_group, _ = Group.objects.get_or_create(name="financial")
        financial_group.user_set.add(cls.user)

        token = cls.client.post(
            reverse("da_token_obtain_pair"),
            content_type="application/json",
            data={"username": "test", "password": "123"},
        )
        cls.cookies = token.cookies

    def setUp(self):
        for key, morsel in self.cookies.items():
            self.client.cookies[key] = morsel.value

    def _create_invoice(self, name="Invoice"):
        return Invoice.objects.create(
            name=name,
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            value=Decimal("100.00"),
            value_open=Decimal("100.00"),
            user=self.user,
            active=True,
        )

    def test_get_payments_month_returns_grouped_data_with_expected_fields(self):
        invoice = self._create_invoice()
        month_start = date.today().replace(day=1)
        previous_month = month_start - timedelta(days=1)
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Debit",
            date=month_start,
            payment_date=month_start + timedelta(days=1),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )
        Payment.objects.create(
            type=Payment.TYPE_CREDIT,
            name="Credit",
            date=month_start,
            payment_date=month_start + timedelta(days=2),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("25.00"),
            status=Payment.STATUS_DONE,
            user=self.user,
            invoice=invoice,
        )
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Debit previous month",
            date=previous_month,
            payment_date=previous_month,
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("5.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(reverse("financial_get_payments_month"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 2)
        row = payload[1]

        expected_fields = [
            "id",
            "name",
            "date",
            "dateTimestamp",
            "total",
            "total_value_credit",
            "total_value_debit",
            "total_value_open",
            "total_value_closed",
            "total_payments",
        ]
        for field in expected_fields:
            self.assertIn(field, row)

        self.assertEqual(row["total_value_credit"], 25.0)
        self.assertEqual(row["total_value_debit"], 10.0)
        self.assertEqual(row["total"], 35.0)
        self.assertEqual(row["total_payments"], 2)

    def test_get_payments_month_supports_date_range(self):
        invoice = self._create_invoice()
        month_start = date.today().replace(day=1)
        previous_month = month_start - timedelta(days=10)

        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Current month",
            date=month_start,
            payment_date=month_start + timedelta(days=2),
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("20.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Previous month",
            date=previous_month,
            payment_date=previous_month,
            installments=1,
            fixed=False,
            active=True,
            value=Decimal("30.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
            invoice=invoice,
        )

        response = self.client.get(
            reverse("financial_get_payments_month"),
            data={"date_from": month_start.isoformat(), "date_to": (month_start + timedelta(days=20)).isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["total_value_debit"], 20.0)

    def test_get_payments_month_rejects_invalid_period(self):
        response = self.client.get(
            reverse("financial_get_payments_month"),
            data={"date_from": "2026-02-10", "date_to": "2026-02-01"},
        )

        self.assertEqual(response.status_code, 400)
