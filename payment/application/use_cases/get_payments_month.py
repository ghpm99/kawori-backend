from datetime import datetime

from django.db.models import Case, Count, DecimalField, Sum, Value, When
from django.db.models.functions import TruncMonth

from payment.models import Payment

MONTHS_PT_BR = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


class GetPaymentsMonthUseCase:
    def execute(self, user, date_from=None, date_to=None):
        invoices_query = Payment.objects.filter(
            invoice__active=True, invoice__user=user, active=True
        )
        if date_from:
            invoices_query = invoices_query.filter(payment_date__gte=date_from)
        if date_to:
            invoices_query = invoices_query.filter(payment_date__lte=date_to)

        invoices = (
            invoices_query.annotate(payment_month=TruncMonth("payment_date"))
            .values("payment_month")
            .annotate(
                total_value_credit=Sum(
                    Case(
                        When(type=0, then="value"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                total_value_debit=Sum(
                    Case(
                        When(type=1, then="value"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                total_value_open=Sum(
                    Case(
                        When(status=Payment.STATUS_OPEN, then="value"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                total_value_closed=Sum(
                    Case(
                        When(status=Payment.STATUS_DONE, then="value"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                total_payments=Count("id"),
            )
            .order_by("payment_month")
        )

        payments = []
        for index, row in enumerate(invoices, start=1):
            month_date = (
                row["payment_month"].date()
                if hasattr(row["payment_month"], "date")
                else row["payment_month"]
            )
            total_value_credit = float(row["total_value_credit"] or 0)
            total_value_debit = float(row["total_value_debit"] or 0)
            total_value_open = float(row["total_value_open"] or 0)
            total_value_closed = float(row["total_value_closed"] or 0)
            total_payments = row["total_payments"]

            payments.append(
                {
                    "id": index,
                    "name": MONTHS_PT_BR[month_date.month - 1],
                    "date": month_date,
                    "dateTimestamp": int(
                        datetime.combine(month_date, datetime.min.time()).timestamp()
                    ),
                    "total": total_value_credit + total_value_debit,
                    "total_value_credit": total_value_credit,
                    "total_value_debit": total_value_debit,
                    "total_value_open": total_value_open,
                    "total_value_closed": total_value_closed,
                    "total_payments": total_payments,
                }
            )

        return {"data": payments}
