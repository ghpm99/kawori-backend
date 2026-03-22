from django.db.models import Case, DecimalField, Q, Sum, Value, When

from payment.models import Payment


class StatementUseCase:
    def execute(self, user, date_from, date_to):
        base_filter = Q(user=user, status=Payment.STATUS_DONE)

        prior_payments = Payment.objects.filter(base_filter, payment_date__lt=date_from)
        prior_agg = prior_payments.aggregate(
            credits=Sum(
                Case(
                    When(type=Payment.TYPE_CREDIT, then="value"),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ),
            debits=Sum(
                Case(
                    When(type=Payment.TYPE_DEBIT, then="value"),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ),
        )
        opening_balance = float((prior_agg["credits"] or 0) - (prior_agg["debits"] or 0))

        period_payments = (
            Payment.objects.filter(
                base_filter,
                payment_date__gte=date_from,
                payment_date__lte=date_to,
            )
            .select_related("invoice")
            .prefetch_related("invoice__tags")
            .order_by("payment_date", "id")
        )

        transactions = []
        running_balance = opening_balance
        total_credits = 0.0
        total_debits = 0.0

        for payment in period_payments:
            value = float(payment.value or 0)
            if payment.type == Payment.TYPE_CREDIT:
                running_balance += value
                total_credits += value
            else:
                running_balance -= value
                total_debits += value

            invoice_name = None
            tags = []
            if payment.invoice:
                invoice_name = payment.invoice.name
                tags = [
                    {"id": tag.id, "name": tag.name, "color": tag.color}
                    for tag in payment.invoice.tags.all()
                ]

            transactions.append(
                {
                    "id": payment.id,
                    "name": payment.name,
                    "description": payment.description,
                    "payment_date": (
                        payment.payment_date.isoformat()
                        if payment.payment_date
                        else None
                    ),
                    "date": payment.date.isoformat() if payment.date else None,
                    "type": payment.type,
                    "value": value,
                    "running_balance": round(running_balance, 2),
                    "invoice_name": invoice_name,
                    "tags": tags,
                }
            )

        transactions.reverse()
        closing_balance = running_balance

        return {
            "data": {
                "summary": {
                    "opening_balance": round(opening_balance, 2),
                    "total_credits": round(total_credits, 2),
                    "total_debits": round(total_debits, 2),
                    "closing_balance": round(closing_balance, 2),
                },
                "transactions": transactions,
            }
        }
