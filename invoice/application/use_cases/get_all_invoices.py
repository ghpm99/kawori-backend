from datetime import datetime, timedelta


class GetAllInvoicesUseCase:
    def execute(
        self,
        request_query,
        user,
        invoice_model,
        paginate_fn,
        boolean_fn,
        format_date_fn,
    ):
        filters = {}

        status = request_query.get("status")
        if status:
            if status == "open":
                filters["value_open__gt"] = 0.0
            if status == "done":
                filters["value_open"] = 0.0
        if request_query.get("type"):
            filters["type"] = request_query.get("type")
        if request_query.get("fixed"):
            filters["fixed"] = boolean_fn(request_query.get("fixed"))
        if request_query.get("name__icontains"):
            filters["name__icontains"] = request_query.get("name__icontains")
        if request_query.get("installments"):
            filters["installments"] = request_query.get("installments")
        if request_query.get("date__gte"):
            filters["date__gte"] = format_date_fn(
                request_query.get("date__gte")
            ) or datetime(2018, 1, 1)
        if request_query.get("date__lte"):
            filters["date__lte"] = format_date_fn(
                request_query.get("date__lte")
            ) or datetime.now() + timedelta(days=1)
        if request_query.get("payment_date__gte"):
            filters["payment_date__gte"] = format_date_fn(
                request_query.get("payment_date__gte")
            ) or datetime(2018, 1, 1)
        if request_query.get("payment_date__lte"):
            filters["payment_date__lte"] = format_date_fn(
                request_query.get("payment_date__lte")
            ) or datetime.now() + timedelta(days=1)

        invoices_query = invoice_model.objects.filter(
            **filters, user=user, active=True
        ).order_by("payment_date", "id")

        page_size = request_query.get("page_size", 10)
        data = paginate_fn(invoices_query, request_query.get("page"), page_size)

        invoices = [
            {
                "id": invoice.id,
                "status": invoice.status,
                "name": invoice.name,
                "installments": invoice.installments,
                "value": float(invoice.value or 0),
                "value_open": float(invoice.value_open or 0),
                "value_closed": float(invoice.value_closed or 0),
                "date": invoice.date,
                "next_payment": invoice.payment_date,
                "tags": [
                    {
                        "id": tag.id,
                        "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
                        "color": tag.color,
                        "is_budget": hasattr(tag, "budget"),
                    }
                    for tag in invoice.tags.all().order_by("budget", "name")
                ],
            }
            for invoice in data.get("data")
        ]

        data["page_size"] = page_size
        data["data"] = invoices
        return {"data": data}
