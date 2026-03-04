from django.urls import path

from audit import views

urlpatterns = [
    path("", views.get_audit_logs, name="audit_get_all"),
    path("stats/", views.get_audit_stats, name="audit_stats"),
    path("report/", views.get_audit_report, name="audit_report"),
]
