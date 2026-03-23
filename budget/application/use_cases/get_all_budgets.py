from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Sum

from payment.models import Payment


class GetAllBudgetsUseCase:
    def execute(
        self,
        user,
        period_query,
        budget_model,
        payment_model,
        get_period_filter_fn,
        date_class,
    ):
        filters = get_period_filter_fn(query_params={"period": period_query})

        budgets = (
            budget_model.objects.filter(user=user)
            .exclude(tag__name__icontains="Entradas")
            .select_related("tag")
        )

        total_earned = payment_model.objects.filter(
            payment_date__gte=filters["start"],
            payment_date__lte=filters["end"],
            type=Payment.TYPE_CREDIT,
            user=user,
            active=True,
        ).aggregate(total=Sum("value"))["total"] or Decimal(0)

        if total_earned == 0:
            today = date_class.today()
            start_current_month = date_class(today.year, today.month, 1)
            start_previous_month = (start_current_month - timedelta(days=1)).replace(
                day=1
            )

            recent_fixed = payment_model.objects.filter(
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

            predicted_fixed_total = payment_model.objects.filter(
                type=Payment.TYPE_CREDIT,
                user=user,
                fixed=True,
                payment_date__in=last_dates,
                active=True,
            ).aggregate(total=Sum("value"))["total"] or Decimal(0)

            total_earned = predicted_fixed_total

        debit_totals = (
            payment_model.objects.filter(
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
            estimated_expense = float(
                (budget.allocation_percentage / 100) * total_earned
            )
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

        return {"data": data}
