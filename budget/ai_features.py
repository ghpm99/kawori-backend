from __future__ import annotations

import calendar
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.functions import Coalesce

from budget.models import Budget
from payment.models import Payment


ESSENTIAL_KEYWORDS = {
    "moradia",
    "aluguel",
    "casa",
    "saude",
    "saude",
    "educacao",
    "transporte",
    "mercado",
    "alimentacao",
}


DISCRETIONARY_KEYWORDS = {
    "lazer",
    "entretenimento",
    "assinatura",
    "delivery",
    "viagem",
    "restaurante",
    "compras",
}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower().strip()
    return normalized


def _parse_period(period: str | None) -> tuple[date, date, str]:
    if period:
        try:
            month, year = map(int, period.split("/"))
            begin = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end = date(year, month, last_day)
            return begin, end, f"{month:02d}/{year}"
        except (ValueError, TypeError):
            pass

    today = date.today()
    begin = today.replace(day=1)
    return begin, today, begin.strftime("%m/%Y")


def _normalize_allocations(raw_allocations: dict[int, float]) -> dict[int, float]:
    total = sum(max(value, 0.0) for value in raw_allocations.values())
    if total <= 0:
        if not raw_allocations:
            return {}
        equal_share = 100.0 / len(raw_allocations)
        return {key: round(equal_share, 2) for key in raw_allocations.keys()}

    normalized = {key: (max(value, 0.0) / total) * 100 for key, value in raw_allocations.items()}

    rounded = {key: round(value, 2) for key, value in normalized.items()}
    diff = round(100.0 - sum(rounded.values()), 2)
    if rounded and diff != 0:
        first_key = next(iter(rounded.keys()))
        rounded[first_key] = round(rounded[first_key] + diff, 2)

    return rounded


def _scenario_multiplier(tag_name: str, scenario: str) -> float:
    normalized_name = _normalize_text(tag_name)

    is_essential = any(keyword in normalized_name for keyword in ESSENTIAL_KEYWORDS)
    is_discretionary = any(keyword in normalized_name for keyword in DISCRETIONARY_KEYWORDS)

    if scenario == "conservative":
        if is_essential:
            return 1.08
        if is_discretionary:
            return 0.88
        return 1.0

    if scenario == "aggressive":
        if is_essential:
            return 0.95
        if is_discretionary:
            return 1.12
        return 1.0

    return 1.0


def _build_tag_reason(current: float, historical: float, scenario: str) -> str:
    delta = historical - current

    if scenario == "conservative":
        return "cenario conservador prioriza categorias essenciais e reduz variaveis"

    if scenario == "aggressive":
        return "cenario agressivo aumenta espaco para categorias discricionarias"

    if delta > 2:
        return "tendencia de gasto acima da alocacao atual nos ultimos 6 meses"
    if delta < -2:
        return "gasto historico abaixo da alocacao atual nos ultimos 6 meses"
    return "alocacao alinhada com comportamento recente"


def build_budget_allocation_suggestions(user, period: str | None = None) -> dict[str, Any]:
    begin, end, period_label = _parse_period(period)

    budgets = list(
        Budget.objects.filter(user=user)
        .exclude(tag__name__icontains="Entradas")
        .select_related("tag")
        .order_by("tag__name")
    )

    if not budgets:
        return {
            "period": period_label,
            "recommended_scenario": "base",
            "scenarios": [],
        }

    history_start = (begin - relativedelta(months=5)).replace(day=1)

    debit_rows = list(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(history_start, end),
            invoice__tags__isnull=False,
        )
        .values("invoice__tags")
        .annotate(total=Coalesce(Sum("value"), Decimal("0")))
    )

    historical_totals = {row["invoice__tags"]: float(row["total"] or 0) for row in debit_rows}
    total_historical = sum(historical_totals.values())

    current_allocations = {budget.tag_id: float(budget.allocation_percentage) for budget in budgets}

    historical_percentages = {}
    for budget in budgets:
        tag_total = historical_totals.get(budget.tag_id, 0.0)
        if total_historical > 0:
            historical_percentages[budget.tag_id] = (tag_total / total_historical) * 100
        else:
            historical_percentages[budget.tag_id] = current_allocations.get(budget.tag_id, 0.0)

    base_raw = {}
    for budget in budgets:
        tag_id = budget.tag_id
        current_value = current_allocations.get(tag_id, 0.0)
        historical_value = historical_percentages.get(tag_id, current_value)
        base_raw[tag_id] = (current_value * 0.55) + (historical_value * 0.45)

    base_allocations = _normalize_allocations(base_raw)

    conservative_raw = {}
    aggressive_raw = {}

    for budget in budgets:
        tag_id = budget.tag_id
        base_value = base_allocations.get(tag_id, 0.0)

        conservative_raw[tag_id] = base_value * _scenario_multiplier(budget.tag.name, "conservative")
        aggressive_raw[tag_id] = base_value * _scenario_multiplier(budget.tag.name, "aggressive")

    scenario_allocations = {
        "conservative": _normalize_allocations(conservative_raw),
        "base": base_allocations,
        "aggressive": _normalize_allocations(aggressive_raw),
    }

    scenario_labels = {
        "conservative": "Conservador",
        "base": "Base",
        "aggressive": "Agressivo",
    }

    scenario_summaries = {
        "conservative": "maior protecao para gastos essenciais",
        "base": "equilibrio entre historico e alocacao atual",
        "aggressive": "mais flexibilidade para gastos discricionarios",
    }

    scenarios = []
    for scenario_id in ("conservative", "base", "aggressive"):
        allocations = []

        for budget in budgets:
            tag_id = budget.tag_id
            current_value = round(current_allocations.get(tag_id, 0.0), 2)
            suggested_value = round(scenario_allocations[scenario_id].get(tag_id, 0.0), 2)
            historical_value = round(historical_percentages.get(tag_id, current_value), 2)

            allocations.append(
                {
                    "budget_id": budget.id,
                    "tag_id": budget.tag_id,
                    "tag_name": budget.tag.name,
                    "current_percentage": current_value,
                    "suggested_percentage": suggested_value,
                    "delta": round(suggested_value - current_value, 2),
                    "reason": _build_tag_reason(current_value, historical_value, scenario_id),
                }
            )

        scenarios.append(
            {
                "id": scenario_id,
                "label": scenario_labels[scenario_id],
                "summary": scenario_summaries[scenario_id],
                "allocations": allocations,
            }
        )

    return {
        "period": period_label,
        "recommended_scenario": "base",
        "scenarios": scenarios,
        "history_window": {
            "date_from": history_start.isoformat(),
            "date_to": end.isoformat(),
        },
    }
