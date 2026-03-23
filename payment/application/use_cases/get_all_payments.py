from kawori.utils import boolean, paginate
from payment.models import Payment


class GetAllPaymentsUseCase:
    def __init__(self, get_status_filter):
        self._get_status_filter = get_status_filter

    def execute(self, user, params):
        filters = {}

        if params.get("status"):
            status_filter = self._get_status_filter(params.get("status"))
            if status_filter is not None:
                filters["status"] = status_filter
        if params.get("type"):
            filters["type"] = params.get("type")
        if params.get("name__icontains"):
            filters["name__icontains"] = params.get("name__icontains")
        if params.get("date__gte"):
            filters["date__gte"] = params.get("date__gte_parsed")
        if params.get("date__lte"):
            filters["date__lte"] = params.get("date__lte_parsed")
        if params.get("installments"):
            filters["installments"] = params.get("installments")
        if params.get("payment_date__gte"):
            filters["payment_date__gte"] = params.get("payment_date__gte_parsed")
        if params.get("payment_date__lte"):
            filters["payment_date__lte"] = params.get("payment_date__lte_parsed")
        if params.get("fixed"):
            filters["fixed"] = boolean(params.get("fixed"))
        if params.get("active"):
            filters["active"] = boolean(params.get("active"))
        if params.get("invoice_id"):
            filters["invoice_id"] = params.get("invoice_id")
        if params.get("invoice"):
            filters["invoice__name__icontains"] = params.get("invoice")

        payments_query = Payment.objects.filter(**filters, user=user).order_by(
            "payment_date", "id"
        )
        page_size = params.get("page_size", 10)

        data = paginate(payments_query, params.get("page", 1), page_size)

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
                "active": payment.active,
                "value": float(payment.value or 0),
                "invoice_id": payment.invoice.id,
                "invoice_name": payment.invoice.name,
                "tags": [
                    {
                        "id": tag.id,
                        "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
                        "color": tag.color,
                        "is_budget": hasattr(tag, "budget"),
                    }
                    for tag in payment.invoice.tags.all().order_by("budget", "name")
                ],
            }
            for payment in data.get("data")
        ]

        data["page_size"] = page_size
        data["data"] = payments

        return {"data": data}
