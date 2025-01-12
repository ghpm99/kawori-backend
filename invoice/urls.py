from django.urls import path, include
from . import views

invoice_details_urls = [
    path("", views.detail_invoice_view, name="invoice_detail"),
    path("payments/", views.detail_invoice_payments_view, name="invoice_payments"),
    path("tags", views.save_tag_invoice_view, name="invoice_tags"),
]

urlpatterns = [
    path("", views.get_all_invoice_view, name="invoice_get_all"),
    path("<int:id>/", include(invoice_details_urls)),
]
