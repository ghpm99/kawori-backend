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
]
