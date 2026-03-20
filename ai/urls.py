from django.urls import path

from ai import views

urlpatterns = [
    path("metrics/overview/", views.metrics_overview, name="ai_metrics_overview"),
    path("metrics/breakdown/", views.metrics_breakdown, name="ai_metrics_breakdown"),
    path("metrics/timeseries/", views.metrics_timeseries, name="ai_metrics_timeseries"),
    path("metrics/events/", views.metrics_events, name="ai_metrics_events"),
]
