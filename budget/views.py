import calendar
import json
from datetime import date, datetime

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from budget.ai_features import build_budget_allocation_suggestions
from budget.application.use_cases.get_ai_allocation_suggestions import (
    GetAIAllocationSuggestionsUseCase,
)
from budget.application.use_cases.get_all_budgets import GetAllBudgetsUseCase
from budget.application.use_cases.reset_budget_allocation import (
    ResetBudgetAllocationUseCase,
)
from budget.application.use_cases.save_budget import SaveBudgetUseCase
from budget.interfaces.api.serializers.budget_serializers import (
    BudgetPeriodQuerySerializer,
)
from budget.models import Budget
from budget.services import DEFAULT_BUDGETS
from kawori.decorators import validate_user
from payment.models import Payment


def get_period_filter(query_params: dict) -> dict:
    period = query_params.get("period")

    if period is None or len(period.split("/")) != 2:
        date_referrer = datetime.now().date()
        start_date = date_referrer.replace(day=1)
        final_date = date_referrer
        return {
            "start": start_date,
            "end": final_date,
        }

    month, year = map(int, period.split("/"))

    start_date = datetime(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    final_date = datetime(year, month, last_day_num)

    return {"start": start_date, "end": final_date}


@require_GET
@validate_user("financial")
def get_all_budgets_view(request, user):
    serializer = BudgetPeriodQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)

    return JsonResponse(
        GetAllBudgetsUseCase().execute(
            user=user,
            period_query=serializer.validated_data.get("period"),
            budget_model=Budget,
            payment_model=Payment,
            get_period_filter_fn=get_period_filter,
            date_class=date,
        )
    )


@require_POST
@validate_user("financial")
@audit_log("budget.update", CATEGORY_FINANCIAL, "Budget")
def save_budget_view(request, user):
    data = json.loads(request.body)
    payload, status_code = SaveBudgetUseCase().execute(
        user=user,
        budget_model=Budget,
        payload=data,
    )
    return JsonResponse(payload, status=status_code)


@require_GET
@validate_user("financial")
@audit_log("budget.reset", CATEGORY_FINANCIAL, "Budget")
def reset_budget_allocation_view(request, user):
    payload, status_code = ResetBudgetAllocationUseCase().execute(
        user=user,
        budget_model=Budget,
        default_budgets=DEFAULT_BUDGETS,
    )
    return JsonResponse(payload, status=status_code)


@require_GET
@validate_user("financial")
def ai_allocation_suggestions_view(request, user):
    serializer = BudgetPeriodQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)
    return JsonResponse(
        GetAIAllocationSuggestionsUseCase().execute(
            user=user,
            period=serializer.validated_data.get("period"),
            build_budget_allocation_suggestions_fn=build_budget_allocation_suggestions,
        )
    )
