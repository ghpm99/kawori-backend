from payment.models import Payment


class ReportTopExpensesUseCase:
    def execute(self, user, date_from, date_to, limit, payment_status_to_label_fn):
        payments = (
            Payment.objects.filter(
                user=user,
                active=True,
                type=Payment.TYPE_DEBIT,
                payment_date__range=(date_from, date_to),
            )
            .select_related("invoice")
            .prefetch_related("invoice__tags")
            .order_by("-value", "payment_date")[:limit]
        )

        data = []
        for payment in payments:
            category = None
            if payment.invoice_id:
                category = (
                    payment.invoice.tags.order_by("name")
                    .values_list("name", flat=True)
                    .first()
                )

            data.append(
                {
                    "id": payment.id,
                    "description": payment.description or payment.name,
                    "category": category,
                    "amount": float(payment.value or 0),
                    "due_date": payment.payment_date,
                    "status": payment_status_to_label_fn(payment.status),
                }
            )

        return data
