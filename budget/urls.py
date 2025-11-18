from django.urls import path
from . import views

urlpatterns = [
    path("", views.get_all_budgets_view, name="budget_get_all_budgets"),
    path("save", views.save_budget_view, name="budget_save_budget"),
    path("reset", views.reset_budget_allocation_view, name="budget_reset_budget_allocation"),
]
