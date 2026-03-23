from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from payment.models import Payment


class ReportTagEvolutionUseCase:
    def execute(self, user, date_from, date_to, compare_with_previous_period=True):
        current_rows = (
            Payment.objects.filter(
                user=user,
                active=True,
                type=Payment.TYPE_DEBIT,
                payment_date__range=(date_from, date_to),
                invoice__tags__isnull=False,
            )
            .values("invoice__tags__id", "invoice__tags__name")
            .annotate(amount=Coalesce(Sum("value"), Decimal("0")))
        )

        current_data = {
            row["invoice__tags__id"]: {
                "tag_id": row["invoice__tags__id"],
                "tag_name": row["invoice__tags__name"],
                "current_amount": float(row["amount"] or 0),
            }
            for row in current_rows
        }

        previous_data = {}
        if compare_with_previous_period:
            period_days = (date_to - date_from).days + 1
            previous_end = date_from - timedelta(days=1)
            previous_begin = previous_end - timedelta(days=period_days - 1)

            previous_rows = (
                Payment.objects.filter(
                    user=user,
                    active=True,
                    type=Payment.TYPE_DEBIT,
                    payment_date__range=(previous_begin, previous_end),
                    invoice__tags__isnull=False,
                )
                .values("invoice__tags__id")
                .annotate(amount=Coalesce(Sum("value"), Decimal("0")))
            )
            previous_data = {
                row["invoice__tags__id"]: float(row["amount"] or 0)
                for row in previous_rows
            }

        data = []
        for item in current_data.values():
            previous_amount = previous_data.get(item["tag_id"], 0.0)
            if previous_amount == 0:
                variation_percent = 100.0 if item["current_amount"] > 0 else 0.0
            else:
                variation_percent = (
                    (item["current_amount"] - previous_amount) / abs(previous_amount)
                ) * 100

            data.append(
                {
                    "tag_id": item["tag_id"],
                    "tag_name": item["tag_name"],
                    "current_amount": item["current_amount"],
                    "previous_amount": (
                        previous_amount if compare_with_previous_period else 0.0
                    ),
                    "variation_percent": (
                        round(variation_percent, 1)
                        if compare_with_previous_period
                        else 0.0
                    ),
                }
            )

        data.sort(key=lambda item: item["current_amount"], reverse=True)
        return data
