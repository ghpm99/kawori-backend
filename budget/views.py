import calendar
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from budget.ai_features import build_budget_allocation_suggestions
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
    filters = get_period_filter(query_params=request.GET)

    budgets = (
        Budget.objects.filter(user=user)
        .exclude(tag__name__icontains="Entradas")
        .select_related("tag")
    )

    total_earned = Payment.objects.filter(
        payment_date__gte=filters["start"],
        payment_date__lte=filters["end"],
        type=Payment.TYPE_CREDIT,
        user=user,
        active=True,
    ).aggregate(total=Sum("value"))["total"] or Decimal(0)

    if total_earned == 0:
        today = date.today()
        start_current_month = date(today.year, today.month, 1)
        start_previous_month = (start_current_month - timedelta(days=1)).replace(day=1)

        recent_fixed = Payment.objects.filter(
            user=user,
            type=Payment.TYPE_CREDIT,
            fixed=True,
            active=True,
            payment_date__gte=start_previous_month,
        )

        last_fixed = (
            recent_fixed.order_by("name")
            .values("name")
            .annotate(last_date=Max("payment_date"))
        )

        last_dates = [item["last_date"] for item in last_fixed]

        predicted_fixed_total = Payment.objects.filter(
            type=Payment.TYPE_CREDIT,
            user=user,
            fixed=True,
            payment_date__in=last_dates,
            active=True,
        ).aggregate(total=Sum("value"))["total"] or Decimal(0)

        total_earned = predicted_fixed_total

    debit_totals = (
        Payment.objects.filter(
            payment_date__gte=filters["start"],
            payment_date__lte=filters["end"],
            type=Payment.TYPE_DEBIT,
            user=user,
            active=True,
        )
        .values("invoice__tags")
        .annotate(total=Sum("value"))
    )

    debit_map = {
        item["invoice__tags"]: item["total"] or Decimal(0) for item in debit_totals
    }

    data = []
    for budget in budgets:
        tag_id = budget.tag_id

        allocation_percentage = float(budget.allocation_percentage)
        estimated_expense = float((budget.allocation_percentage / 100) * total_earned)
        actual_expense = float(debit_map.get(tag_id, Decimal(0)))

        data.append(
            {
                "id": budget.id,
                "name": budget.tag.name,
                "color": budget.tag.color,
                "allocation_percentage": allocation_percentage,
                "estimated_expense": estimated_expense,
                "actual_expense": actual_expense,
            }
        )

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
@audit_log("budget.update", CATEGORY_FINANCIAL, "Budget")
def save_budget_view(request, user):
    data = json.loads(request.body)
    with transaction.atomic():
        for item in data.get("data", []):
            budget = Budget.objects.filter(id=item.get("id"), user=user).first()
            if budget:
                budget.allocation_percentage = item.get(
                    "allocation_percentage", budget.allocation_percentage
                )
                budget.save()

    return JsonResponse({"msg": "Orçamento atualizado com sucesso"})


@require_GET
@validate_user("financial")
@audit_log("budget.reset", CATEGORY_FINANCIAL, "Budget")
def reset_budget_allocation_view(request, user):
    with transaction.atomic():
        budget_list = Budget.objects.filter(user=user)
        for budget in budget_list:
            for default_budget in DEFAULT_BUDGETS:
                if budget.tag.name.lower() == default_budget["name"].lower():
                    budget.allocation_percentage = default_budget[
                        "allocation_percentage"
                    ]
                    budget.save()
                    break

    return JsonResponse({"msg": "Orçamentos resetados com sucesso"})


@require_GET
@validate_user("financial")
def ai_allocation_suggestions_view(request, user):
    period = request.GET.get("period")
    result = build_budget_allocation_suggestions(user=user, period=period)
    return JsonResponse(result)
