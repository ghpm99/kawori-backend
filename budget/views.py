import calendar
import json
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum, Max
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

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

    # 1) Lista de budgets + anotação da tag (1 query)
    budgets = Budget.objects.filter(user=user).select_related("tag")

    # 2) Total de créditos (1 query)
    total_earned = Payment.objects.filter(
        payment_date__gte=filters["start"],
        payment_date__lte=filters["end"],
        type=Payment.TYPE_CREDIT,
        user=user,
        active=True,
    ).aggregate(total=Sum("value"))["total"] or Decimal(0)

    # 2. Se não há créditos (futuro), usar previsões de FIXED
    if total_earned == 0:
        # Busca a última versão de cada pagamento fixo
        last_fixed = (
            Payment.objects.filter(type=Payment.TYPE_CREDIT, user=user, fixed=True, active=True)
            .order_by("name")  # agrupa por name ou outra chave identificadora
            .values("name")
            .annotate(last_date=Max("payment_date"))
        )

        # Lista de datas dos últimos pagamentos fixos
        last_dates = [item["last_date"] for item in last_fixed]

        # Buscar os valores exatos desses últimos pagamentos fixos
        predicted_fixed_total = Payment.objects.filter(
            type=Payment.TYPE_CREDIT, user=user, fixed=True, payment_date__in=last_dates, active=True
        ).aggregate(total=Sum("value"))["total"] or Decimal(0)

        total_earned = predicted_fixed_total

    # 3) Total de débitos agrupado por tag (1 query)
    debit_totals = (
        Payment.objects.filter(
            payment_date__gte=filters["start"],
            payment_date__lte=filters["end"],
            type=Payment.TYPE_DEBIT,
            user=user,
            active=True,
        )
        .values("invoice__tags")  # agrupa pela tag
        .annotate(total=Sum("value"))  # soma por tag
    )

    # Transformar em dict fácil de acessar
    debit_map = {item["invoice__tags"]: item["total"] or Decimal(0) for item in debit_totals}

    # 4) Montar resultado final sem consultas adicionais
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
def save_budget_view(request, user):
    data = json.loads(request.body)
    for item in data.get("data", []):
        budget = Budget.objects.filter(id=item.get("id"), user=user).first()
        if budget:
            budget.allocation_percentage = item.get("allocation_percentage", budget.allocation_percentage)
            budget.save()

    return JsonResponse({"msg": "Orçamento atualizado com sucesso"})


@require_GET
@validate_user("financial")
def reset_budget_allocation_view(request, user):
    budget_list = Budget.objects.filter(user=user)
    for budget in budget_list:
        for default_budget in DEFAULT_BUDGETS:
            if budget.tag.name.lower() == default_budget["name"].lower():
                budget.allocation_percentage = default_budget["allocation_percentage"]
                budget.save()
                break

    return JsonResponse({"msg": "Orçamentos resetados com sucesso"})
