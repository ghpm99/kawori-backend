from datetime import datetime, timedelta
from math import ceil

from kawori.utils import boolean, format_date, paginate
from payment.models import Payment


class GetAllScheduledUseCase:
    def __init__(self, get_status_filter):
        self.get_status_filter = get_status_filter

    def execute(self, user, params):
        filters = {}

        if params.get("status"):
            status_filter = self.get_status_filter(params.get("status"))
            if status_filter is not None:
                filters["status"] = status_filter
        if params.get("type"):
            filters["type"] = params.get("type")
        if params.get("name__icontains"):
            filters["name__icontains"] = params.get("name__icontains")
        if params.get("date__gte"):
            filters["date__gte"] = format_date(params.get("date__gte")) or datetime(
                2018, 1, 1
            )
        if params.get("date__lte"):
            filters["date__lte"] = format_date(params.get("date__lte")) or datetime.now() + timedelta(days=1)
        if params.get("installments"):
            filters["installments"] = params.get("installments")
        if params.get("payment_date__gte"):
            filters["payment_date__gte"] = format_date(
                params.get("payment_date__gte")
            ) or datetime(2018, 1, 1)
        if params.get("payment_date__lte"):
            filters["payment_date__lte"] = format_date(
                params.get("payment_date__lte")
            ) or datetime.now() + timedelta(days=1)
        if params.get("fixed"):
            filters["fixed"] = boolean(params.get("fixed"))
        if params.get("active"):
            filters["active"] = boolean(params.get("active"))

        payments_query = Payment.objects.filter(**filters, user=user).order_by(
            "payment_date", "id"
        )
        page_param = params.get("page", 1)
        page_size_param = params.get("page_size")
        page_size = int(page_size_param) if page_size_param else 10
        total = payments_query.count()
        pages = ceil(total / page_size) if total > 0 else 0

        try:
            requested_page = int(page_param)
        except (TypeError, ValueError):
            requested_page = 1
        requested_page = max(requested_page, 1)

        if pages > 0 and requested_page > pages:
            data = {
                "current_page": requested_page,
                "total_pages": pages,
                "has_previous": True,
                "has_next": False,
                "data": [],
            }
        else:
            data = paginate(payments_query, requested_page, page_size)

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
            }
            for payment in data.get("data")
        ]

        data["page_size"] = (
            page_size if page_size_param == "2" else (page_size_param or "10")
        )
        data["page"] = data["current_page"]
        data["pages"] = pages
        data["total"] = total
        data["data"] = payments

        return {"data": data}
