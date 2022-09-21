from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.get_all_view, name='financial_get_all'),
    path('<int:id>/', include([
        path('', views.detail_view, name='financial_detail_view'),
        path('save', views.save_detail_view, name='financial_save_detail_view'),
        path('payoff', views.payoff_detail_view, name='financial_payoff_detail_view')
    ])),
    path('report', views.report_payment_view, name='financial_report_payment_view'),
    path('new-payment', views.save_new_view, name='financial_save_new'),
    path('contract/', include([
        path('', views.get_all_contract_view, name='financial_get_all_contract'),
        path('new', views.save_new_contract_view, name='financial_save_new_contract'),
        path('<int:id>/', include([
            path('', views.detail_contract_view, name='financial_detail_contract'),
            path('invoice/', views.include_new_invoice_view, name='financial_new_invoice'),
            path('merge/', views.merge_contract_view, name='financial_merge_contract')
        ]))
    ])),
    path('invoice/', include([
        path('', views.get_all_invoice_view, name='financial_get_all_invoice'),
        path('<int:id>/', include([
            path('', views.detail_invoice_view, name='financial_detail_invoice'),
            path('tags', views.save_tag_invoice_view, name='financial_invoice_tags'),
        ]))
    ])),
    path('tag/', include([
        path('', views.get_all_tag_view, name='financial_get_all_tags'),
        path('new', views.include_new_tag_view, name='financial_include_tag'),
    ]))
]
