from django.urls import include, path

from . import views

contract_details_urls = [
    path("", views.detail_contract_view, name="financial_detail_contract"),
    path("invoices/", views.detail_contract_invoices_view, name="financial_detail_contract_invoices"),
    path("invoice/", views.include_new_invoice_view, name="financial_new_invoice"),
    path("merge/", views.merge_contract_view, name="financial_merge_contract"),
]

urlpatterns = [
    path("", views.get_all_contract_view, name="financial_get_all_contract"),
    path("new", views.save_new_contract_view, name="financial_save_new_contract"),
    path("<int:id>/", include(contract_details_urls)),
    path("update_all_contracts_value", views.update_all_contracts_value, name="financial_update_all_contracts_value"),
]
