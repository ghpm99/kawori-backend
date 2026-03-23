from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from payment.models import Payment


class ReportDailyCashFlowUseCase:
    def execute(self, user, date_from, date_to):
        grouped = (
            Payment.objects.filter(
                user=user,
                active=True,
                payment_date__range=(date_from, date_to),
            )
            .values("payment_date")
            .annotate(
                credit=Coalesce(
                    Sum("value", filter=Q(type=Payment.TYPE_CREDIT)), Decimal("0")
                ),
                debit=Coalesce(
                    Sum("value", filter=Q(type=Payment.TYPE_DEBIT)), Decimal("0")
                ),
            )
            .order_by("payment_date")
        )

        by_date = {row["payment_date"]: row for row in grouped}
        cursor = date_from
        accumulated = 0.0
        data = []
        total_credit = 0.0
        total_debit = 0.0

        while cursor <= date_to:
            row = by_date.get(cursor)
            credit = float((row or {}).get("credit") or 0)
            debit = float((row or {}).get("debit") or 0)
            net = credit - debit
            accumulated += net
            total_credit += credit
            total_debit += debit

            data.append(
                {
                    "date": cursor,
                    "credit": credit,
                    "debit": debit,
                    "net": net,
                    "accumulated": accumulated,
                }
            )
            cursor = cursor + timedelta(days=1)

        return {
            "data": data,
            "summary": {
                "total_credit": total_credit,
                "total_debit": total_debit,
                "net": total_credit - total_debit,
            },
        }
