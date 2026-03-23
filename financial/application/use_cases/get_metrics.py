from payment.models import Payment


class GetMetricsUseCase:
    def _percent_change(self, current, previous):
        if previous == 0:
            return 0
        return round(((current - previous) / abs(previous)) * 100, 2)

    def execute(
        self,
        user,
        date_from,
        date_to,
        get_total_payment_fn,
        get_total_payment_from_date_fn,
    ):
        if date_from and date_to:
            revenues_current, revenues_last_month = get_total_payment_from_date_fn(
                date_from, date_to, user.id, Payment.TYPE_CREDIT
            )
            expenses_current, expenses_last_month = get_total_payment_from_date_fn(
                date_from, date_to, user.id, Payment.TYPE_DEBIT
            )
        else:
            revenues_current = get_total_payment_fn(user.id, Payment.TYPE_CREDIT)
            expenses_current = get_total_payment_fn(user.id, Payment.TYPE_DEBIT)
            revenues_last_month = 0
            expenses_last_month = 0

        revenue_data = {
            "value": revenues_current,
            "metric_value": self._percent_change(revenues_current, revenues_last_month),
        }

        expenses_data = {
            "value": expenses_current,
            "metric_value": self._percent_change(expenses_current, expenses_last_month),
        }

        profit_current = revenues_current - expenses_current
        profit_last_month = revenues_last_month - expenses_last_month

        profit_data = {
            "value": profit_current,
            "metric_value": self._percent_change(profit_current, profit_last_month),
        }

        growth_data = {"value": self._percent_change(profit_current, profit_last_month)}

        return {
            "revenues": revenue_data,
            "expenses": expenses_data,
            "profit": profit_data,
            "growth": growth_data,
        }
