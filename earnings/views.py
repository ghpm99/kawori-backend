from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection

from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import Payment


def get_status_filter(status_params):
    if status_params == "all" or status_params == "":
        return None

    if status_params == "open" or status_params == "0":
        return Payment.STATUS_OPEN

    if status_params == "done" or status_params == "1":
        return Payment.STATUS_DONE

    return None


@require_GET
@validate_user("financial")
def get_all_view(request, user):
    req = request.GET
    filters = {"type": Payment.TYPE_CREDIT}

    if req.get("status"):
        status_filter = get_status_filter(req.get("status"))
        if status_filter is not None:
            filters["status"] = status_filter
    if req.get("type"):
        filters["type"] = req.get("type")
    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")
    if req.get("date__gte"):
        filters["date__gte"] = format_date(req.get("date__gte")) or datetime(2018, 1, 1)
    if req.get("date__lte"):
        filters["date__lte"] = format_date(req.get("date__lte")) or datetime.now() + timedelta(days=1)
    if req.get("installments"):
        filters["installments"] = req.get("installments")
    if req.get("payment_date__gte"):
        filters["payment_date__gte"] = format_date(req.get("payment_date__gte")) or datetime(2018, 1, 1)
    if req.get("payment_date__lte"):
        filters["payment_date__lte"] = format_date(req.get("payment_date__lte")) or datetime.now() + timedelta(days=1)
    if req.get("fixed"):
        filters["fixed"] = boolean(req.get("fixed"))
    if req.get("active"):
        filters["active"] = boolean(req.get("active"))
    if req.get("contract"):
        filters["invoice__contract__name__icontains"] = req.get("contract")

    payments_query = Payment.objects.filter(**filters, user=user).order_by("payment_date", "id")
    page_size = req.get("page_size", 10)

    data = paginate(payments_query, req.get("page", 1), page_size)

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
            "contract_id": payment.invoice.contract.id,
            "contract_name": payment.invoice.contract.name,
        }
        for payment in data.get("data")
    ]

    data["page_size"] = page_size
    data["data"] = payments

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def get_total_view(request, user):
    date_referrer = datetime.now().date()

    begin = date_referrer.replace(day=1)
    end = (date_referrer + relativedelta(months=1, day=1)) - timedelta(days=1)

    sum_payment_value = """
        SELECT
            COALESCE(SUM(value), 0) as total_earnings
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=%(type)s
            AND fp.active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(sum_payment_value, {
            "begin": begin,
            "end": end,
            "type": Payment.TYPE_CREDIT,
            "user_id": user.id
        })
        total_earning_current = float(cursor.fetchone()[0])

    end = begin - timedelta(days=1)
    begin = end.replace(day=1)

    with connection.cursor() as cursor:
        cursor.execute(sum_payment_value, {
            "begin": begin,
            "end": end,
            "type": Payment.TYPE_CREDIT,
            "user_id": user.id
        })
        total_earning_last_month = float(cursor.fetchone()[0])

    print(total_earning_current)
    print(total_earning_last_month)

    data = {
        "value": total_earning_current,
        "metric_value": ((total_earning_current - total_earning_last_month) / abs(total_earning_last_month)) * 100 if total_earning_last_month != 0 else 0
    }

    return JsonResponse(data)
