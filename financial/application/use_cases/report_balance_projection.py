from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from payment.models import Payment


class ReportBalanceProjectionUseCase:
    def execute(self, user, start_date, months_ahead):
        start_month = start_date.replace(day=1)
        data = []

        for i in range(months_ahead):
            month_start = start_month + relativedelta(months=i)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

            sums = Payment.objects.filter(
                user=user,
                active=True,
                payment_date__range=(month_start, month_end),
            ).aggregate(
                credit=Coalesce(
                    Sum("value", filter=Q(type=Payment.TYPE_CREDIT)), Decimal("0")
                ),
                debit=Coalesce(
                    Sum("value", filter=Q(type=Payment.TYPE_DEBIT)), Decimal("0")
                ),
            )

            projected_credit = float(sums["credit"] or 0)
            projected_debit = float(sums["debit"] or 0)
            projected_balance = projected_credit - projected_debit

            if projected_balance < 0:
                risk_level = "high"
            elif projected_credit > 0 and (projected_balance / projected_credit) < 0.1:
                risk_level = "medium"
            else:
                risk_level = "low"

            data.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "projected_credit": projected_credit,
                    "projected_debit": projected_debit,
                    "projected_balance": projected_balance,
                    "risk_level": risk_level,
                }
            )

        return {
            "data": data,
            "assumptions": {
                "includes_open_payments": True,
                "includes_fixed_entries": True,
            },
        }
