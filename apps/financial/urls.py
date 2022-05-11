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
    path('new-payment', views.save_new_view, name='financial_save_new')
]
