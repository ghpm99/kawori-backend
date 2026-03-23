from datetime import datetime, timedelta


class GetInvoicePaymentsUseCase:
    def execute(
        self,
        request_query,
        invoice_id,
        user,
        payment_model,
        paginate_fn,
        get_status_filter_fn,
        format_date_fn,
        boolean_fn,
    ):
        filters = {"invoice": invoice_id}

        if request_query.get("status"):
            status_filter = get_status_filter_fn(request_query.get("status"))
            if status_filter is not None:
                filters["status"] = status_filter
        if request_query.get("type"):
            filters["type"] = request_query.get("type")
        if request_query.get("name__icontains"):
            filters["name__icontains"] = request_query.get("name__icontains")
        if request_query.get("date__gte"):
            filters["date__gte"] = format_date_fn(
                request_query.get("date__gte")
            ) or datetime(2018, 1, 1)
        if request_query.get("date__lte"):
            filters["date__lte"] = format_date_fn(
                request_query.get("date__lte")
            ) or datetime.now() + timedelta(days=1)
        if request_query.get("installments"):
            filters["installments"] = request_query.get("installments")
        if request_query.get("payment_date__gte"):
            filters["payment_date__gte"] = format_date_fn(
                request_query.get("payment_date__gte")
            ) or datetime(2018, 1, 1)
        if request_query.get("payment_date__lte"):
            filters["payment_date__lte"] = format_date_fn(
                request_query.get("payment_date__lte")
            ) or datetime.now() + timedelta(days=1)
        if request_query.get("fixed"):
            filters["fixed"] = boolean_fn(request_query.get("fixed"))
        if request_query.get("active"):
            filters["active"] = boolean_fn(request_query.get("active"))

        payments_query = payment_model.objects.filter(**filters, user=user).order_by(
            "id"
        )
        page_size = request_query.get("page_size", 10)
        data = paginate_fn(payments_query, request_query.get("page"), page_size)

        payments = [
            {
                "id": payment.id,
                "status": payment.status,
                "type": payment.type,
                "name": payment.name,
                "date": payment.date,
                "installments": payment.installments,
                "payment_date": payment.payment_date,
                "fixed": payment.fixed,
                "value": float(payment.value or 0),
            }
            for payment in data.get("data")
        ]

        data["page_size"] = page_size
        data["data"] = payments
        return {"data": data}
