from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.functions import Coalesce

from payment.models import Payment

SEVERITY_ORDER = {
    "critical": 3,
    "attention": 2,
    "info": 1,
}


MONTHS_PT_BR_SHORT = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    return None


def _parse_period_string(value: Any) -> tuple[date, date] | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    parts = raw.split("/")
    if len(parts) != 2:
        return None

    try:
        month = int(parts[0])
        year = int(parts[1])
    except ValueError:
        return None

    if month < 1 or month > 12:
        return None

    begin = date(year, month, 1)
    end = (begin + relativedelta(months=1)) - timedelta(days=1)
    return begin, end


def _resolve_period(payload: dict[str, Any]) -> tuple[date, date]:
    date_from = _parse_date(payload.get("date_from"))
    date_to = _parse_date(payload.get("date_to"))

    period_payload = payload.get("period")
    if isinstance(period_payload, dict):
        date_from = date_from or _parse_date(period_payload.get("date_from"))
        date_to = date_to or _parse_date(period_payload.get("date_to"))
    elif period_payload is not None:
        parsed_period = _parse_period_string(period_payload)
        if parsed_period is not None:
            date_from = date_from or parsed_period[0]
            date_to = date_to or parsed_period[1]

    today = date.today()
    default_begin = today.replace(day=1)

    begin = date_from or default_begin
    end = date_to or today

    if begin > end:
        begin, end = end, begin

    return begin, end


def _period_label(begin: date, end: date) -> str:
    if begin.month == end.month and begin.year == end.year:
        return f"{MONTHS_PT_BR_SHORT[begin.month - 1]}/{begin.year}"

    return f"{MONTHS_PT_BR_SHORT[begin.month - 1]}/{begin.year}-{MONTHS_PT_BR_SHORT[end.month - 1]}/{end.year}"


def _to_currency(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _build_spending_variation_insight(
    user, begin: date, end: date
) -> dict[str, Any] | None:
    current_total = _to_currency(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(begin, end),
        ).aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
    )

    period_start = begin.replace(day=1)
    previous_window_end = period_start - timedelta(days=1)
    previous_window_begin = (period_start - relativedelta(months=3)).replace(day=1)

    previous_total = _to_currency(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(previous_window_begin, previous_window_end),
        ).aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
    )

    previous_average = previous_total / 3 if previous_total > 0 else 0.0
    if previous_average <= 0:
        return None

    variation = ((current_total - previous_average) / previous_average) * 100
    if abs(variation) < 12:
        return None

    if variation > 0:
        severity = "attention" if variation >= 25 else "info"
        title = "Aumento atipico de despesas"
        action = (
            "revisar gastos variaveis e definir limite semanal para categorias em alta"
        )
    else:
        severity = "info"
        title = "Reducao relevante de despesas"
        action = "consolidar a economia atual em uma meta mensal de poupanca"

    metric = f"{variation:+.0f}%"
    context = (
        f"comparacao {_period_label(begin, end)} vs media "
        f"{_period_label(previous_window_begin, previous_window_end)}"
    )

    confidence = min(0.97, 0.68 + min(abs(variation), 60) / 150)

    return {
        "severity": severity,
        "title": title,
        "metric": metric,
        "context": context,
        "action": action,
        "confidence": round(confidence, 2),
    }


def _build_tag_concentration_insight(
    user, begin: date, end: date
) -> dict[str, Any] | None:
    rows = list(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(begin, end),
            invoice__tags__isnull=False,
        )
        .values("invoice__tags__name")
        .annotate(amount=Coalesce(Sum("value"), Decimal("0")))
        .order_by("-amount")
    )

    if not rows:
        return None

    total_amount = sum(_to_currency(item["amount"]) for item in rows)
    if total_amount <= 0:
        return None

    top_rows = rows[:2]
    top_share = (
        sum(_to_currency(item["amount"]) for item in top_rows) / total_amount
    ) * 100
    if top_share < 55:
        return None

    top_names = [item.get("invoice__tags__name") or "Sem tag" for item in top_rows]
    title = "Concentracao alta em poucas tags"
    metric = f"{top_share:.0f}%"
    context = f"{len(top_rows)} tags concentram a maior parte das despesas do periodo"
    action = (
        f"revisar recorrencias de {', '.join(top_names)} e ajustar teto por categoria"
    )

    confidence = min(0.95, 0.62 + min(top_share, 85) / 220)

    return {
        "severity": "attention",
        "title": title,
        "metric": metric,
        "context": context,
        "action": action,
        "confidence": round(confidence, 2),
    }


def _build_overdue_risk_insight(user, begin: date, end: date) -> dict[str, Any] | None:
    today = date.today()

    overdue_qs = Payment.objects.filter(
        user=user,
        active=True,
        type=Payment.TYPE_DEBIT,
        status=Payment.STATUS_OPEN,
        payment_date__range=(begin, end),
        payment_date__lt=today,
    )

    overdue_count = overdue_qs.count()
    overdue_amount = _to_currency(
        overdue_qs.aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
    )
    if overdue_count == 0 or overdue_amount <= 0:
        return None

    period_debit = _to_currency(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(begin, end),
        ).aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
    )

    ratio = (overdue_amount / period_debit) * 100 if period_debit > 0 else 0

    if overdue_count >= 3 or ratio >= 25:
        severity = "critical"
    else:
        severity = "attention"

    confidence = min(0.96, 0.65 + min(ratio, 80) / 200)

    return {
        "severity": severity,
        "title": "Pagamentos em atraso pressionando o fluxo",
        "metric": f"{overdue_count} em atraso",
        "context": f"R$ {overdue_amount:.2f} pendentes ({ratio:.1f}% do periodo)",
        "action": "priorizar quitacao de vencidos e renegociar os de maior impacto",
        "confidence": round(confidence, 2),
    }


def generate_financial_ai_insights(
    user, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = payload or {}
    begin, end = _resolve_period(payload)

    insights = []

    spending_insight = _build_spending_variation_insight(user, begin, end)
    if spending_insight is not None:
        insights.append(spending_insight)

    concentration_insight = _build_tag_concentration_insight(user, begin, end)
    if concentration_insight is not None:
        insights.append(concentration_insight)

    overdue_insight = _build_overdue_risk_insight(user, begin, end)
    if overdue_insight is not None:
        insights.append(overdue_insight)

    if not insights:
        insights.append(
            {
                "severity": "info",
                "title": "Periodo estavel",
                "metric": "0 alertas criticos",
                "context": "nao foram detectadas variacoes relevantes no periodo",
                "action": "manter rotina atual e revisar metas no proximo fechamento",
                "confidence": 0.78,
            }
        )

    insights.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 0),
            item.get("confidence", 0),
        ),
        reverse=True,
    )

    return {
        "priority_insights": insights,
        "period": {
            "date_from": begin.isoformat(),
            "date_to": end.isoformat(),
        },
    }
