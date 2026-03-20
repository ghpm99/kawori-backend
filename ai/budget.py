from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone


class BudgetDecision:
    def __init__(self, allowed: bool, reason: str = "") -> None:
        self.allowed = allowed
        self.reason = reason


def check_budget(
    feature_name: str | None, user_id: int | None = None
) -> BudgetDecision:
    if not feature_name:
        return BudgetDecision(True)

    try:
        from ai.models import AIBudgetPolicy, AIExecutionEvent
    except Exception:
        return BudgetDecision(True)

    policy = AIBudgetPolicy.objects.filter(
        feature_name=feature_name, active=True
    ).first()
    if policy is None:
        return BudgetDecision(True)

    today = timezone.now().date()
    month_start = date(today.year, today.month, 1)

    feature_daily_spent = _sum_cost(
        AIExecutionEvent.objects.filter(
            feature_name=feature_name, created_at__date=today, success=True
        )
    )
    feature_monthly_spent = _sum_cost(
        AIExecutionEvent.objects.filter(
            feature_name=feature_name, created_at__date__gte=month_start, success=True
        )
    )

    if (
        policy.daily_limit_usd is not None
        and feature_daily_spent >= policy.daily_limit_usd
    ):
        return BudgetDecision(False, "feature_daily_limit")
    if (
        policy.monthly_limit_usd is not None
        and feature_monthly_spent >= policy.monthly_limit_usd
    ):
        return BudgetDecision(False, "feature_monthly_limit")

    if user_id is None:
        return BudgetDecision(True)

    user_daily_spent = _sum_cost(
        AIExecutionEvent.objects.filter(
            feature_name=feature_name,
            created_at__date=today,
            user_id=user_id,
            success=True,
        )
    )
    user_monthly_spent = _sum_cost(
        AIExecutionEvent.objects.filter(
            feature_name=feature_name,
            created_at__date__gte=month_start,
            user_id=user_id,
            success=True,
        )
    )

    if (
        policy.user_daily_limit_usd is not None
        and user_daily_spent >= policy.user_daily_limit_usd
    ):
        return BudgetDecision(False, "user_daily_limit")
    if (
        policy.user_monthly_limit_usd is not None
        and user_monthly_spent >= policy.user_monthly_limit_usd
    ):
        return BudgetDecision(False, "user_monthly_limit")

    return BudgetDecision(True)


def _sum_cost(queryset) -> Decimal:
    value = queryset.aggregate(total=Sum("cost_estimate")).get("total")
    return value if value is not None else Decimal("0")
