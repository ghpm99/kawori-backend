from django.urls import include, path

from . import views

payment_details_urls = [
    path("", views.detail_view, name="financial_detail_view"),
    path("save", views.save_detail_view, name="financial_save_detail_view"),
    path("payoff", views.payoff_detail_view, name="financial_payoff_detail_view"),
]

urlpatterns = [
    path("", views.get_all_view, name="financial_get_all"),
    path("new/", views.save_new_view, name="financial_save_new"),
    path("month/", views.get_payments_month, name="financial_get_payments_month"),
    path("<int:id>/", include(payment_details_urls)),
    path("statement/", views.statement_view, name="financial_statement"),
    path(
        "statement/anomalies",
        views.statement_anomalies_view,
        name="financial_statement_anomalies",
    ),
    path("scheduled", views.get_all_scheduled_view, name="financial_get_all_scheduled"),
    path("csv-mapping/", views.get_csv_mapping, name="financial_get_csv_mapping"),
    path("csv-ai-map/", views.csv_ai_map_view, name="financial_csv_ai_map"),
    path(
        "csv-ai-normalize/",
        views.csv_ai_normalize_view,
        name="financial_csv_ai_normalize",
    ),
    path(
        "csv-ai-reconcile/",
        views.csv_ai_reconcile_view,
        name="financial_csv_ai_reconcile",
    ),
    path(
        "ai-tag-suggestions/",
        views.ai_tag_suggestions_view,
        name="financial_ai_tag_suggestions",
    ),
    path("process-csv/", views.process_csv_upload, name="financial_process_csv_upload"),
    path(
        "csv-resolve-imports/",
        views.csv_resolve_imports_view,
        name="financial_csv_resolve_imports_view",
    ),
    path("csv-import/", views.csv_import_view, name="financial_csv_import_view"),
]
