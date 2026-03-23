import inspect
import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from contract.models import Contract
from financial import views
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag


class FinancialViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="financial-reg", email="financial-reg@test.com", password="123"
        )

    def setUp(self):
        self.rf = RequestFactory()

    def _mock_cursor(self, *, fetchone_side_effect=None, fetchall_side_effect=None):
        cursor = MagicMock()
        if fetchone_side_effect is not None:
            cursor.fetchone.side_effect = fetchone_side_effect
        if fetchall_side_effect is not None:
            cursor.fetchall.side_effect = fetchall_side_effect

        ctx = MagicMock()
        ctx.__enter__.return_value = cursor
        return ctx, cursor

    def _call(self, fn, method="get", data=None):
        payload = None if data is None else json.dumps(data)
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method(
                "/", data=payload, content_type="application/json"
            )
        return inspect.unwrap(fn)(request, user=self.user)

    def test_report_count_and_amount_views(self):
        ctx, _ = self._mock_cursor(
            fetchone_side_effect=[(3,), (120.5,), (20.0,), (10.0,)]
        )
        with patch("financial.views.connection.cursor", return_value=ctx):
            count_res = self._call(views.report_count_payment_view)
            amount_res = self._call(views.report_amount_payment_view)
            open_res = self._call(views.report_amount_payment_open_view)
            closed_res = self._call(views.report_amount_payment_closed_view)

        self.assertEqual(count_res.status_code, 200)
        self.assertEqual(json.loads(count_res.content)["data"], 3)
        self.assertEqual(json.loads(amount_res.content)["data"], 120.5)
        self.assertEqual(json.loads(open_res.content)["data"], 20.0)
        self.assertEqual(json.loads(closed_res.content)["data"], 10.0)

    def test_report_count_payment_view_counts_all_active_payments_without_default_period(
        self,
    ):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(7,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_count_payment_view)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], 7)
        query, params = cursor.execute.call_args.args
        self.assertNotIn("type=1", query)
        self.assertNotIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(params, {"user_id": self.user.id})

    def test_report_count_payment_view_applies_date_range_when_provided(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(4,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(
                views.report_count_payment_view,
                data={"date_from": "2026-02-01", "date_to": "2026-02-28"},
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.execute.call_args.args
        self.assertIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params,
            {
                "user_id": self.user.id,
                "begin": datetime(2026, 2, 1),
                "end": datetime(2026, 2, 28),
            },
        )

    def test_report_count_payment_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_count_payment_view,
            data={"date_from": "2026-02-01", "date_to": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_amount_payment_view_sums_all_active_payments_without_default_period(
        self,
    ):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(180.5,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_amount_payment_view)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], 180.5)
        query, params = cursor.execute.call_args.args
        self.assertNotIn("type=1", query)
        self.assertNotIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(params, {"user_id": self.user.id})

    def test_report_amount_payment_view_applies_date_range_when_provided(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(90.0,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(
                views.report_amount_payment_view,
                data={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.execute.call_args.args
        self.assertIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params,
            {
                "user_id": self.user.id,
                "begin": datetime(2026, 3, 1),
                "end": datetime(2026, 3, 31),
            },
        )

    def test_report_amount_payment_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_amount_payment_view,
            data={"date_from": "2026-03-02", "date_to": "2026-03-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_amount_payment_open_view_sums_all_open_payments_without_default_period(
        self,
    ):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(35.0,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_amount_payment_open_view)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], 35.0)
        query, params = cursor.execute.call_args.args
        self.assertNotIn("type=1", query)
        self.assertNotIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(params, {"user_id": self.user.id})

    def test_report_amount_payment_open_view_applies_date_range_when_provided(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(12.0,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(
                views.report_amount_payment_open_view,
                data={"date_from": "2026-04-01", "date_to": "2026-04-30"},
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.execute.call_args.args
        self.assertIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params,
            {
                "user_id": self.user.id,
                "begin": datetime(2026, 4, 1),
                "end": datetime(2026, 4, 30),
            },
        )

    def test_report_amount_payment_open_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_amount_payment_open_view,
            data={"date_from": "2026-04-02", "date_to": "2026-04-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_amount_payment_closed_view_sums_all_closed_payments_without_default_period(
        self,
    ):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(78.0,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_amount_payment_closed_view)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], 78.0)
        query, params = cursor.execute.call_args.args
        self.assertNotIn("type=1", query)
        self.assertNotIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(params, {"user_id": self.user.id})

    def test_report_amount_payment_closed_view_applies_date_range_when_provided(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(44.0,)])

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(
                views.report_amount_payment_closed_view,
                data={"date_from": "2026-05-01", "date_to": "2026-05-31"},
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.execute.call_args.args
        self.assertIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params,
            {
                "user_id": self.user.id,
                "begin": datetime(2026, 5, 1),
                "end": datetime(2026, 5, 31),
            },
        )

    def test_report_amount_payment_closed_view_returns_error_when_period_is_invalid(
        self,
    ):
        response = self._call(
            views.report_amount_payment_closed_view,
            data={"date_from": "2026-05-02", "date_to": "2026-05-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_amount_invoice_by_tag_view(self):
        tags_rows = [(1, "Tag A", "#111111", 50), (2, "Tag B", "#222222", 25.5)]
        ctx, cursor = self._mock_cursor(fetchall_side_effect=[tags_rows])
        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_amount_invoice_by_tag_view)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["name"], "Tag A")
        self.assertEqual(payload[1]["amount"], 25.5)
        query, params = cursor.execute.call_args.args
        self.assertIn("fp.type=%(payment_type)s", query)
        self.assertNotIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params, {"user_id": self.user.id, "payment_type": Payment.TYPE_DEBIT}
        )

    def test_report_amount_invoice_by_tag_view_applies_date_range_when_provided(self):
        ctx, cursor = self._mock_cursor(
            fetchall_side_effect=[[(1, "Moradia", "#1677ff", 2300)]]
        )
        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(
                views.report_amount_invoice_by_tag_view,
                data={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            )

        self.assertEqual(response.status_code, 200)
        query, params = cursor.execute.call_args.args
        self.assertIn("BETWEEN %(begin)s AND %(end)s", query)
        self.assertEqual(
            params,
            {
                "user_id": self.user.id,
                "payment_type": Payment.TYPE_DEBIT,
                "begin": datetime(2026, 6, 1),
                "end": datetime(2026, 6, 30),
            },
        )

    def test_report_amount_invoice_by_tag_view_returns_error_when_period_is_invalid(
        self,
    ):
        response = self._call(
            views.report_amount_invoice_by_tag_view,
            data={"date_from": "2026-06-02", "date_to": "2026-06-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_forecast_amount_value_view_empty_and_non_empty(self):
        empty_ctx, empty_cursor = self._mock_cursor(fetchone_side_effect=[(0, 0)])
        with patch("financial.views.connection.cursor", return_value=empty_ctx):
            empty_response = self._call(views.report_forecast_amount_value)

        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(json.loads(empty_response.content)["data"], 0)
        empty_query, empty_params = empty_cursor.execute.call_args.args
        self.assertNotIn("BETWEEN %(begin)s", empty_query)
        self.assertEqual(empty_params, {"user_id": self.user.id})

        values_ctx, values_cursor = self._mock_cursor(fetchone_side_effect=[(100.0, 4)])
        with patch("financial.views.connection.cursor", return_value=values_ctx):
            response = self._call(
                views.report_forecast_amount_value,
                data={"date_from": "2026-07-01", "date_to": "2026-07-31"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], 100.0)
        query, params = values_cursor.execute.call_args.args
        self.assertNotIn("BETWEEN %(begin)s", query)
        self.assertEqual(params, {"user_id": self.user.id})

    def test_report_forecast_amount_value_view_returns_error_when_period_is_invalid(
        self,
    ):
        response = self._call(
            views.report_forecast_amount_value,
            data={"date_from": "2026-07-02", "date_to": "2026-07-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_payment_view_builds_summary_payload(self):
        payments_rows = [
            ("2026-01-01", 10, 5, 5, 5, 15),
            ("2026-02-01", 20, 10, 10, 10, 25),
        ]
        ctx, cursor = self._mock_cursor(
            fetchall_side_effect=[payments_rows], fetchone_side_effect=[(33,), (12,)]
        )
        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_payment_view)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]
        self.assertEqual(len(data["payments"]), 2)
        self.assertEqual(data["fixed_debit"], 33.0)
        self.assertEqual(data["fixed_credit"], 12.0)
        self.assertEqual(
            cursor.execute.call_args_list[0].args[1], {"user_id": self.user.id}
        )
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1], {"user_id": self.user.id}
        )
        self.assertEqual(
            cursor.execute.call_args_list[2].args[1], {"user_id": self.user.id}
        )

    def test_report_payment_view_applies_period_to_summary_and_fixed_totals(self):
        payments_rows = [("2026-01-01", 10, 5, 5, 5, 15)]
        ctx, cursor = self._mock_cursor(
            fetchall_side_effect=[payments_rows], fetchone_side_effect=[(11,), (7,)]
        )
        filters = {"date_from": "2026-01-01", "date_to": "2026-01-31"}

        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.report_payment_view, data=filters)

        self.assertEqual(response.status_code, 200)
        expected_params = {
            "user_id": self.user.id,
            "begin": datetime(2026, 1, 1),
            "end": datetime(2026, 1, 31),
        }
        self.assertEqual(cursor.execute.call_args_list[0].args[1], expected_params)
        self.assertEqual(cursor.execute.call_args_list[1].args[1], expected_params)
        self.assertEqual(cursor.execute.call_args_list[2].args[1], expected_params)

    def test_report_payment_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_payment_view,
            data={"date_from": "2026-02-01", "date_to": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_get_total_payment_from_date_reads_current_and_last_month(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(200,), (50,)])
        with patch("financial.views.connection.cursor", return_value=ctx):
            current, previous = views.get_total_payment_from_date(
                date(2026, 3, 1), date(2026, 3, 31), self.user.id, 1
            )

        self.assertEqual(current, 200.0)
        self.assertEqual(previous, 50.0)
        self.assertEqual(cursor.execute.call_count, 2)

    def test_get_total_payment_reads_full_history_total(self):
        ctx, cursor = self._mock_cursor(fetchone_side_effect=[(320,)])
        with patch("financial.views.connection.cursor", return_value=ctx):
            total = views.get_total_payment(self.user.id, Payment.TYPE_CREDIT)

        self.assertEqual(total, 320.0)
        self.assertEqual(cursor.execute.call_count, 1)

    def test_get_metrics_view_uses_payment_totals(self):
        with patch(
            "financial.views.get_total_payment_from_date",
            side_effect=[(1000.0, 500.0), (600.0, 400.0)],
        ):
            response = self._call(
                views.get_metrics_view,
                data={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["revenues"]["value"], 1000.0)
        self.assertEqual(data["expenses"]["value"], 600.0)
        self.assertEqual(data["profit"]["value"], 400.0)
        self.assertEqual(data["revenues"]["metric_value"], 100.0)
        self.assertEqual(data["expenses"]["metric_value"], 50.0)
        self.assertEqual(data["profit"]["metric_value"], 300.0)
        self.assertEqual(data["growth"]["value"], 300.0)

    def test_get_metrics_view_handles_zero_last_month(self):
        with patch(
            "financial.views.get_total_payment_from_date",
            side_effect=[(100.0, 0.0), (10.0, 0.0)],
        ):
            response = self._call(
                views.get_metrics_view,
                data={"date_from": "2026-03-01", "date_to": "2026-03-31"},
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["revenues"]["metric_value"], 0)
        self.assertEqual(data["expenses"]["metric_value"], 0)
        self.assertEqual(data["growth"]["value"], 0)

    def test_get_metrics_view_uses_full_history_when_period_is_missing(self):
        with patch(
            "financial.views.get_total_payment", side_effect=[300.0, 120.0]
        ) as mocked_total:
            response = self._call(views.get_metrics_view)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["revenues"]["value"], 300.0)
        self.assertEqual(data["expenses"]["value"], 120.0)
        self.assertEqual(data["profit"]["value"], 180.0)
        self.assertEqual(data["revenues"]["metric_value"], 0)
        self.assertEqual(data["expenses"]["metric_value"], 0)
        self.assertEqual(data["profit"]["metric_value"], 0)
        self.assertEqual(data["growth"]["value"], 0)
        self.assertEqual(mocked_total.call_count, 2)

    def test_get_metrics_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.get_metrics_view,
            data={"date_from": "2026-03-02", "date_to": "2026-03-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_daily_cash_flow_view_returns_series_and_summary(self):
        grouped_rows = [
            {
                "payment_date": datetime(2026, 8, 1),
                "credit": Decimal("100.00"),
                "debit": Decimal("20.00"),
            },
            {
                "payment_date": datetime(2026, 8, 3),
                "credit": Decimal("0.00"),
                "debit": Decimal("10.00"),
            },
        ]
        queryset = MagicMock()
        queryset.values.return_value.annotate.return_value.order_by.return_value = (
            grouped_rows
        )

        with patch("financial.views.Payment.objects.filter", return_value=queryset):
            response = self._call(
                views.report_daily_cash_flow_view,
                data={"date_from": "2026-08-01", "date_to": "2026-08-03"},
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["data"]), 3)
        self.assertEqual(payload["data"][0]["credit"], 100.0)
        self.assertEqual(payload["data"][0]["debit"], 20.0)
        self.assertEqual(payload["data"][1]["credit"], 0)
        self.assertEqual(payload["data"][1]["debit"], 0)
        self.assertEqual(payload["data"][2]["debit"], 10.0)
        self.assertEqual(payload["summary"]["total_credit"], 100.0)
        self.assertEqual(payload["summary"]["total_debit"], 30.0)
        self.assertEqual(payload["summary"]["net"], 70.0)

    def test_report_daily_cash_flow_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_daily_cash_flow_view,
            data={"date_from": "2026-08-03", "date_to": "2026-08-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_daily_cash_flow_view_requires_date_from_and_date_to(self):
        no_from = self._call(
            views.report_daily_cash_flow_view,
            data={"date_to": "2026-08-01"},
        )
        self.assertEqual(no_from.status_code, 400)
        self.assertEqual(
            json.loads(no_from.content), {"msg": "date_from and date_to are required"}
        )

        no_to = self._call(
            views.report_daily_cash_flow_view,
            data={"date_from": "2026-08-01"},
        )
        self.assertEqual(no_to.status_code, 400)
        self.assertEqual(
            json.loads(no_to.content), {"msg": "date_from and date_to are required"}
        )

    def test_report_top_expenses_view_returns_ordered_limited_data(self):
        contract = Contract.objects.create(name="TE", user=self.user)
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="TE Inv",
            date=date(2026, 9, 1),
            installments=1,
            payment_date=date(2026, 9, 1),
            fixed=False,
            active=True,
            value=Decimal("0"),
            value_open=Decimal("0"),
            contract=contract,
            user=self.user,
        )
        tag = Tag.objects.create(name="Moradia", color="#123", user=self.user)
        invoice.tags.add(tag)

        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Despesa Menor",
            description="Conta de agua",
            date=date(2026, 9, 1),
            installments=1,
            payment_date=date(2026, 9, 1),
            fixed=False,
            active=True,
            value=Decimal("50.00"),
            status=Payment.STATUS_DONE,
            reference="x1",
            invoice=invoice,
            user=self.user,
        )
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Despesa Maior",
            description="Aluguel",
            date=date(2026, 9, 2),
            installments=1,
            payment_date=date(2026, 9, 2),
            fixed=False,
            active=True,
            value=Decimal("120.00"),
            status=Payment.STATUS_OPEN,
            reference="x2",
            invoice=invoice,
            user=self.user,
        )

        response = self._call(
            views.report_top_expenses_view,
            data={"date_from": "2026-09-01", "date_to": "2026-09-30", "limit": "1"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["description"], "Aluguel")
        self.assertEqual(data[0]["category"], "Moradia")
        self.assertEqual(data[0]["amount"], 120.0)

    def test_report_top_expenses_view_returns_error_when_period_is_invalid(self):
        response = self._call(
            views.report_top_expenses_view,
            data={"date_from": "2026-09-02", "date_to": "2026-09-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {"msg": "date_from must be less than or equal to date_to"},
        )

    def test_report_top_expenses_view_requires_date_from_and_date_to(self):
        no_from = self._call(
            views.report_top_expenses_view,
            data={"date_to": "2026-09-01"},
        )
        self.assertEqual(no_from.status_code, 400)
        self.assertEqual(
            json.loads(no_from.content), {"msg": "date_from and date_to are required"}
        )

        no_to = self._call(
            views.report_top_expenses_view,
            data={"date_from": "2026-09-01"},
        )
        self.assertEqual(no_to.status_code, 400)
        self.assertEqual(
            json.loads(no_to.content), {"msg": "date_from and date_to are required"}
        )

    def test_report_balance_projection_view_returns_months_and_risk_levels(self):
        queryset = MagicMock()
        queryset.aggregate.side_effect = [
            {"credit": Decimal("100.00"), "debit": Decimal("40.00")},
            {"credit": Decimal("50.00"), "debit": Decimal("80.00")},
        ]

        with patch("financial.views.Payment.objects.filter", return_value=queryset):
            response = self._call(
                views.report_balance_projection_view,
                data={"date_from": "2026-01-15", "months_ahead": "2"},
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["data"][0]["month"], "2026-01")
        self.assertEqual(payload["data"][0]["risk_level"], "low")
        self.assertEqual(payload["data"][1]["month"], "2026-02")
        self.assertEqual(payload["data"][1]["risk_level"], "high")
        self.assertEqual(payload["assumptions"]["includes_open_payments"], True)
        self.assertEqual(payload["assumptions"]["includes_fixed_entries"], True)

    def test_report_balance_projection_view_requires_date_from(self):
        response = self._call(views.report_balance_projection_view, data={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content), {"msg": "date_from is required"})

    def test_report_balance_projection_view_respects_months_ahead_minimum(self):
        queryset = MagicMock()
        queryset.aggregate.side_effect = [
            {"credit": Decimal("0"), "debit": Decimal("0")}
        ] * 6

        with patch("financial.views.Payment.objects.filter", return_value=queryset):
            response = self._call(
                views.report_balance_projection_view,
                data={"date_from": "2026-01-01", "months_ahead": "0"},
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["data"]), 6)

    def test_contract_views_list_detail_and_create(self):
        c1 = Contract.objects.create(
            name="C1", user=self.user, value=10, value_open=8, value_closed=2
        )
        Contract.objects.create(name="C2", user=self.user)

        list_response = self._call(
            views.get_all_contract_view, method="get", data={"page": 1, "page_size": 10}
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(json.loads(list_response.content)["data"]["data"]), 2)

        filtered_response = self._call(
            views.get_all_contract_view,
            method="get",
            data={"id": c1.id, "page_size": 10},
        )
        self.assertEqual(len(json.loads(filtered_response.content)["data"]["data"]), 1)

        detail_response = inspect.unwrap(views.detail_contract_view)(
            self.rf.get("/"), id=c1.id, user=self.user
        )
        self.assertEqual(detail_response.status_code, 200)

        not_found = inspect.unwrap(views.detail_contract_view)(
            self.rf.get("/"), id=99999, user=self.user
        )
        self.assertEqual(not_found.status_code, 404)

        create_response = self._call(
            views.save_new_contract_view, method="post", data={"name": "Created"}
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertTrue(
            Contract.objects.filter(name="Created", user=self.user).exists()
        )

    def test_invoice_views_list_detail_and_payments(self):
        contract = Contract.objects.create(name="IC", user=self.user)
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Inv 1",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 5),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            contract=contract,
            user=self.user,
        )
        tag = Tag.objects.create(name="T1", color="#123", user=self.user)
        invoice.tags.add(tag)
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="P1",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 5),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            reference="r",
            invoice=invoice,
            user=self.user,
        )

        list_response = self._call(
            views.get_all_invoice_view, method="get", data={"page": 1, "page_size": 10}
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(json.loads(list_response.content)["data"]["data"]), 1)

        contract_invoices = inspect.unwrap(views.detail_contract_invoices_view)(
            self.rf.get("/", data={"page": 1, "page_size": 10}),
            id=contract.id,
            user=self.user,
        )
        self.assertEqual(contract_invoices.status_code, 200)
        self.assertEqual(len(json.loads(contract_invoices.content)["data"]["data"]), 1)

        detail_response = inspect.unwrap(views.detail_invoice_view)(
            self.rf.get("/"), id=invoice.id, user=self.user
        )
        self.assertEqual(detail_response.status_code, 200)

        not_found = inspect.unwrap(views.detail_invoice_view)(
            self.rf.get("/"), id=99999, user=self.user
        )
        self.assertEqual(not_found.status_code, 404)

        payments_response = inspect.unwrap(views.detail_invoice_payments_view)(
            self.rf.get("/", data={"page": 1, "page_size": 10}),
            id=invoice.id,
            user=self.user,
        )
        self.assertEqual(payments_response.status_code, 200)
        self.assertEqual(len(json.loads(payments_response.content)["data"]["data"]), 1)

    def test_include_new_invoice_and_tags(self):
        contract = Contract.objects.create(name="NC", user=self.user)
        tag = Tag.objects.create(name="TG", color="#fff", user=self.user)

        with patch("financial.views.generate_payments") as mocked_generate:
            response = inspect.unwrap(views.include_new_invoice_view)(
                self.rf.post(
                    "/",
                    data=json.dumps(
                        {
                            "status": Invoice.STATUS_OPEN,
                            "type": Invoice.Type.DEBIT,
                            "name": "New Invoice",
                            "date": "2026-01-01",
                            "installments": 2,
                            "payment_date": "2026-01-15",
                            "fixed": False,
                            "active": True,
                            "value": 50.0,
                            "tags": [tag.id],
                        }
                    ),
                    content_type="application/json",
                ),
                id=contract.id,
                user=self.user,
            )

        self.assertEqual(response.status_code, 200)
        created = Invoice.objects.get(name="New Invoice")
        self.assertEqual(created.tags.count(), 1)
        mocked_generate.assert_called_once()

        contract.refresh_from_db()
        self.assertEqual(float(contract.value), 50.0)
        self.assertEqual(float(contract.value_open), 50.0)

        not_found = inspect.unwrap(views.include_new_invoice_view)(
            self.rf.post(
                "/", data=json.dumps({"name": "x"}), content_type="application/json"
            ),
            id=99999,
            user=self.user,
        )
        self.assertEqual(not_found.status_code, 404)

    def test_merge_contract_view(self):
        main = Contract.objects.create(name="Main", user=self.user)
        old = Contract.objects.create(name="Old", user=self.user)
        Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Old Inv",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("5.00"),
            value_open=Decimal("5.00"),
            contract=old,
            user=self.user,
        )

        with patch("financial.views.update_contract_value") as mocked_update:
            response = inspect.unwrap(views.merge_contract_view)(
                self.rf.post(
                    "/",
                    data=json.dumps({"contracts": [old.id]}),
                    content_type="application/json",
                ),
                id=main.id,
                user=self.user,
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contract.objects.filter(id=old.id).exists())
        self.assertEqual(Invoice.objects.filter(contract=main).count(), 1)
        mocked_update.assert_called_once()

        not_found = inspect.unwrap(views.merge_contract_view)(
            self.rf.post(
                "/", data=json.dumps({"contracts": []}), content_type="application/json"
            ),
            id=99999,
            user=self.user,
        )
        self.assertEqual(not_found.status_code, 404)

    def test_tag_views(self):
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Tag Invoice",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("1.00"),
            value_open=Decimal("1.00"),
            contract=Contract.objects.create(name="TC", user=self.user),
            user=self.user,
        )
        tag1 = Tag.objects.create(name="Alpha", color="#111", user=self.user)

        all_tags = self._call(views.get_all_tag_view, method="get")
        self.assertEqual(all_tags.status_code, 200)
        self.assertEqual(len(json.loads(all_tags.content)["data"]), 1)

        filtered_tags = self._call(
            views.get_all_tag_view, method="get", data={"name__icontains": "alp"}
        )
        self.assertEqual(len(json.loads(filtered_tags.content)["data"]), 1)

        create_tag = self._call(
            views.include_new_tag_view,
            method="post",
            data={"name": "Beta", "color": "#222"},
        )
        self.assertEqual(create_tag.status_code, 200)
        self.assertTrue(Tag.objects.filter(name="Beta", user=self.user).exists())

        save_tags = inspect.unwrap(views.save_tag_invoice_view)(
            self.rf.post(
                "/", data=json.dumps([tag1.id]), content_type="application/json"
            ),
            id=invoice.id,
            user=self.user,
        )
        self.assertEqual(save_tags.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.tags.count(), 1)

        null_payload = inspect.unwrap(views.save_tag_invoice_view)(
            self.rf.post("/", data="null", content_type="application/json"),
            id=invoice.id,
            user=self.user,
        )
        self.assertEqual(null_payload.status_code, 404)

    def test_payment_list_and_detail_views(self):
        contract = Contract.objects.create(name="PC", user=self.user)
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Payment invoice",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            contract=contract,
            user=self.user,
        )
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Payment detail",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            reference="rp",
            invoice=invoice,
            user=self.user,
        )

        listing = self._call(
            views.get_all_view,
            method="get",
            data={
                "status": Payment.STATUS_OPEN,
                "page": 1,
                "page_size": 10,
                "invoice": "Payment",
            },
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(json.loads(listing.content)["data"]["data"]), 1)

        detail = inspect.unwrap(views.detail_view)(
            self.rf.get("/"), id=payment.id, user=self.user
        )
        self.assertEqual(detail.status_code, 200)

        not_found = inspect.unwrap(views.detail_view)(
            self.rf.get("/"), id=99999, user=self.user
        )
        self.assertEqual(not_found.status_code, 404)

    def test_get_all_view_and_get_all_invoice_view_with_all_filters(self):
        contract = Contract.objects.create(name="Filters", user=self.user)
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Invoice Filter",
            date=date(2026, 1, 1),
            installments=2,
            payment_date=date(2026, 1, 2),
            fixed=True,
            active=True,
            status=Invoice.STATUS_OPEN,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            contract=contract,
            user=self.user,
        )
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Filter payment",
            date=date(2026, 1, 1),
            installments=2,
            payment_date=date(2026, 1, 2),
            fixed=True,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            reference="fp",
            invoice=invoice,
            user=self.user,
        )

        all_view = self._call(
            views.get_all_view,
            method="get",
            data={
                "status": str(Payment.STATUS_OPEN),
                "type": str(Payment.TYPE_DEBIT),
                "name__icontains": "Filter",
                "date__gte": "2026-01-01",
                "date__lte": "2026-01-31",
                "installments": "2",
                "payment_date__gte": "2026-01-01",
                "payment_date__lte": "2026-01-31",
                "fixed": "true",
                "active": "true",
                "invoice": "Invoice",
                "page": 1,
                "page_size": 10,
            },
        )
        self.assertEqual(all_view.status_code, 200)
        self.assertEqual(len(json.loads(all_view.content)["data"]["data"]), 1)

        all_invoice = self._call(
            views.get_all_invoice_view,
            method="get",
            data={
                "status": str(Invoice.STATUS_OPEN),
                "name__icontains": "Invoice",
                "installments": "2",
                "date__gte": "2026-01-01",
                "date__lte": "2026-01-31",
                "page": 1,
                "page_size": 10,
            },
        )
        self.assertEqual(all_invoice.status_code, 200)
        self.assertEqual(len(json.loads(all_invoice.content)["data"]["data"]), 1)

    def test_get_payments_month_view_with_cursor(self):
        rows = [(1, "Contract A", 10, 20, 15, 15, 3)]
        ctx, _ = self._mock_cursor(fetchall_side_effect=[rows])
        with patch("financial.views.connection.cursor", return_value=ctx):
            response = self._call(views.get_payments_month)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["total_payments"], 3)

    def test_save_new_and_save_detail_views(self):
        create_response = self._call(
            views.save_new_view,
            method="post",
            data={
                "type": Payment.TYPE_DEBIT,
                "name": "Created payment",
                "date": "2026-01-01",
                "installments": 2,
                "payment_date": "2026-01-05",
                "fixed": False,
                "value": 20.0,
            },
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(
            Payment.objects.filter(user=self.user, name="Created payment").count(), 2
        )

        contract = Contract.objects.create(
            name="SD", user=self.user, value_open=0, value=0
        )
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="SDI",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            contract=contract,
            user=self.user,
        )
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Editable",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            reference="x",
            invoice=invoice,
            user=self.user,
        )

        update_response = inspect.unwrap(views.save_detail_view)(
            self.rf.post(
                "/",
                data=json.dumps(
                    {
                        "name": "Updated",
                        "fixed": True,
                        "active": False,
                        "value": 30.0,
                        "type": 1,
                        "payment_date": "2026-02-15",
                    }
                ),
                content_type="application/json",
            ),
            id=payment.id,
            user=self.user,
        )
        self.assertEqual(update_response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.name, "Updated")
        self.assertTrue(payment.fixed)
        self.assertFalse(payment.active)
        self.assertEqual(str(payment.payment_date), "2026-02-15")

        done = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Done P",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("1.00"),
            status=Payment.STATUS_DONE,
            reference="done",
            invoice=invoice,
            user=self.user,
        )
        done_response = inspect.unwrap(views.save_detail_view)(
            self.rf.post(
                "/", data=json.dumps({"name": "no"}), content_type="application/json"
            ),
            id=done.id,
            user=self.user,
        )
        self.assertEqual(done_response.status_code, 500)

        not_found = inspect.unwrap(views.save_detail_view)(
            self.rf.post(
                "/", data=json.dumps({"name": "x"}), content_type="application/json"
            ),
            id=99999,
            user=self.user,
        )
        self.assertEqual(not_found.status_code, 404)

    def test_payoff_detail_view_branches(self):
        contract = Contract.objects.create(
            name="PO", user=self.user, value=0, value_open=0, value_closed=0
        )
        invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="POI",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            value_closed=Decimal("0.00"),
            contract=contract,
            user=self.user,
        )
        payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="PO payment",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            status=Payment.STATUS_OPEN,
            reference="po",
            invoice=invoice,
            user=self.user,
        )
        success = inspect.unwrap(views.payoff_detail_view)(
            self.rf.post("/"), id=payment.id, user=self.user
        )
        self.assertEqual(success.status_code, 200)

        already_done = inspect.unwrap(views.payoff_detail_view)(
            self.rf.post("/"), id=payment.id, user=self.user
        )
        self.assertEqual(already_done.status_code, 400)

        not_found = inspect.unwrap(views.payoff_detail_view)(
            self.rf.post("/"), id=99999, user=self.user
        )
        self.assertEqual(not_found.status_code, 400)

        fixed_contract = Contract.objects.create(
            name="PO2", user=self.user, value=0, value_open=0, value_closed=0
        )
        fixed_invoice = Invoice.objects.create(
            type=Invoice.Type.DEBIT,
            name="Fixed",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 10),
            fixed=True,
            active=True,
            value=Decimal("5.00"),
            value_open=Decimal("5.00"),
            value_closed=Decimal("0.00"),
            contract=fixed_contract,
            user=self.user,
        )
        fixed_payment = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Fixed P",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 10),
            fixed=True,
            active=True,
            value=Decimal("5.00"),
            status=Payment.STATUS_OPEN,
            reference="f",
            invoice=fixed_invoice,
            user=self.user,
        )
        with patch("financial.views.generate_payments") as mocked_generate:
            fixed_response = inspect.unwrap(views.payoff_detail_view)(
                self.rf.post("/"), id=fixed_payment.id, user=self.user
            )
        self.assertEqual(fixed_response.status_code, 200)
        mocked_generate.assert_called_once()
