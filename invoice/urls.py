from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.get_all_invoice_view, name="financial_get_all_invoice"),
    path(
        "<int:id>/",
        include(
            [
                path(
                    "",
                    views.detail_invoice_view,
                    name="financial_detail_invoice",
                ),
                path(
                    "payments/",
                    views.detail_invoice_payments_view,
                    name="financial_detail_invoice_payments",
                ),
                path(
                    "tags",
                    views.save_tag_invoice_view,
                    name="financial_invoice_tags",
                ),
            ]
        ),
    ),
]
