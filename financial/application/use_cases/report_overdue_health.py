from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from payment.models import Payment


class ReportOverdueHealthUseCase:
    def execute(self, user, date_from, date_to, reference_date=None):
        current_date = reference_date or date.today()

        overdue_payments = (
            Payment.objects.filter(
                user=user,
                active=True,
                type=Payment.TYPE_DEBIT,
                status=Payment.STATUS_OPEN,
                payment_date__range=(date_from, date_to),
                payment_date__lt=current_date,
            )
            .select_related("invoice")
            .prefetch_related("invoice__tags")
        )

        overdue_count = overdue_payments.count()
        overdue_amount = float(
            overdue_payments.aggregate(total=Coalesce(Sum("value"), Decimal("0")))[
                "total"
            ]
            or 0
        )

        delays = [
            (current_date - payment.payment_date).days for payment in overdue_payments
        ]
        average_delay_days = round((sum(delays) / len(delays)), 1) if delays else 0

        total_period_amount = float(
            Payment.objects.filter(
                user=user,
                active=True,
                type=Payment.TYPE_DEBIT,
                payment_date__range=(date_from, date_to),
            ).aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
            or 0
        )
        overdue_ratio = (
            round((overdue_amount / total_period_amount) * 100, 1)
            if total_period_amount
            else 0
        )

        critical_map = defaultdict(
            lambda: {"category": "", "amount": 0.0, "payment_ids": set()}
        )
        for payment in overdue_payments:
            for tag in payment.invoice.tags.all():
                item = critical_map[tag.id]
                item["category"] = tag.name
                item["amount"] += float(payment.value or 0)
                item["payment_ids"].add(payment.id)

        critical_categories = sorted(
            (
                {
                    "category": item["category"],
                    "amount": item["amount"],
                    "count": len(item["payment_ids"]),
                }
                for item in critical_map.values()
            ),
            key=lambda value: value["amount"],
            reverse=True,
        )[:3]

        return {
            "data": {
                "overdue_count": overdue_count,
                "overdue_amount": overdue_amount,
                "average_delay_days": average_delay_days,
                "overdue_ratio": overdue_ratio,
                "critical_categories": critical_categories,
            }
        }
