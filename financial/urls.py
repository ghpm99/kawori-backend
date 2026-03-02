from django.urls import path
from . import views

urlpatterns = [
    path("", views.report_payment_view, name="financial_report_payment_view"),
    path("count_payment", views.report_count_payment_view, name="financial_report_count_payment"),
    path("amount_payment", views.report_amount_payment_view, name="financial_report_amount_payment"),
    path("amount_payment_open", views.report_amount_payment_open_view, name="financial_report_amount_payment_open"),
    path(
        "amount_payment_closed", views.report_amount_payment_closed_view, name="financial_report_amount_payment_closed"
    ),
    path("amount_invoice_by_tag", views.report_amount_invoice_by_tag_view, name="financial_report_amount_invoice_tag"),
    path("amount_forecast_value", views.report_forecast_amount_value, name="financial_report_amount_forecast_value"),
    path("metrics/", views.get_metrics_view, name="financial_get_metrics_view"),
    path("daily_cash_flow", views.report_daily_cash_flow_view, name="financial_report_daily_cash_flow"),
    path("top_expenses", views.report_top_expenses_view, name="financial_report_top_expenses"),
    path("balance_projection", views.report_balance_projection_view, name="financial_report_balance_projection"),
    path("overdue_health", views.report_overdue_health_view, name="financial_report_overdue_health"),
    path("tag_evolution", views.report_tag_evolution_view, name="financial_report_tag_evolution"),
]
