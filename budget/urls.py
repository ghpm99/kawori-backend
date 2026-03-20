from django.urls import path

from . import views

urlpatterns = [
    path("", views.get_all_budgets_view, name="budget_get_all_budgets"),
    path(
        "ai-allocation-suggestions",
        views.ai_allocation_suggestions_view,
        name="budget_ai_allocation_suggestions",
    ),
    path("save", views.save_budget_view, name="budget_save_budget"),
    path(
        "reset",
        views.reset_budget_allocation_view,
        name="budget_reset_budget_allocation",
    ),
]
