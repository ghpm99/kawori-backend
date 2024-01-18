from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.get_all_view, name='financial_get_all'),
    path('payment/', include([
        path('month/', views.get_payments_month, name='financial_get_payments_month'),
    ])),
    path('<int:id>/', include([
        path('', views.detail_view, name='financial_detail_view'),
        path('save', views.save_detail_view, name='financial_save_detail_view'),
        path('payoff', views.payoff_detail_view, name='financial_payoff_detail_view')
    ])),
    path('report/', include([
        path('', views.report_payment_view, name='financial_report_payment_view'),
        path('count_payment', views.report_count_payment_view, name='financial_report_count_payment'),
        path('amount_payment', views.report_amount_payment_view, name='financial_report_amount_payment'),
        path('amount_payment_open', views.report_amount_payment_open_view, name='financial_report_amount_payment_open'),
        path('amount_payment_closed', views.report_amount_payment_closed_view, name='financial_report_amount_payment_closed'),
        path('amount_invoice_by_tag', views.report_amount_invoice_by_tag_view, name='financial_report_amount_invoice_tag'),
        path('amount_forecast_value', views.report_forecast_amount_value, name='financial_report_amount_forecast_value'),
    ])),
    path('new-payment', views.save_new_view, name='financial_save_new'),
    path('contract/', include([
        path('', views.get_all_contract_view, name='financial_get_all_contract'),
        path('new', views.save_new_contract_view, name='financial_save_new_contract'),
        path('<int:id>/', include([
            path('', views.detail_contract_view, name='financial_detail_contract'),
            path('invoices/', views.detail_contract_invoices_view, name='financial_detail_contract_invoices'),
            path('invoice/', views.include_new_invoice_view, name='financial_new_invoice'),
            path('merge/', views.merge_contract_view, name='financial_merge_contract')
        ]))
    ])),
    path('invoice/', include([
        path('', views.get_all_invoice_view, name='financial_get_all_invoice'),
        path('<int:id>/', include([
            path('', views.detail_invoice_view, name='financial_detail_invoice'),
            path('payments/', views.detail_invoice_payments_view, name='financial_detail_invoice_payments'),
            path('tags', views.save_tag_invoice_view, name='financial_invoice_tags'),
        ]))
    ])),
    path('tag/', include([
        path('', views.get_all_tag_view, name='financial_get_all_tags'),
        path('new', views.include_new_tag_view, name='financial_include_tag'),
    ])),
    path('update_all_contracts_value', views.update_all_contracts_value, name='financial_update_all_contracts_value')
]
