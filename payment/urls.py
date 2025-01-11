from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.get_all_view, name="financial_get_all"),
    path("new/", views.save_new_view, name="financial_save_new"),
    path(
        "month/", views.get_payments_month, name="financial_get_payments_month"
    ),
    path(
        "<int:id>/",
        include(
            [
                path("", views.detail_view, name="financial_detail_view"),
                path(
                    "save",
                    views.save_detail_view,
                    name="financial_save_detail_view",
                ),
                path(
                    "payoff",
                    views.payoff_detail_view,
                    name="financial_payoff_detail_view",
                ),
            ]
        ),
    ),
]
