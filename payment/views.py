import json
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


from financial.utils import calculate_installments, generate_payments
from invoice.models import Invoice
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
    filters = {}

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
        }
        for payment in data.get("data")
    ]

    data["page_size"] = page_size
    data["data"] = payments

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
def save_new_view(request, user):
    data = json.loads(request.body)

    installments = data.get("installments")
    payment_date = data.get("payment_date")

    value_installments = calculate_installments(data.get("value"), installments)

    date_format = "%Y-%m-%d"

    for i in range(installments):
        payment = Payment(
            type=data.get("type"),
            name=data.get("name"),
            date=data.get("date"),
            installments=i + 1,
            payment_date=payment_date,
            fixed=data.get("fixed"),
            value=value_installments[i],
            user=user,
        )
        payment.save()
        date_obj = datetime.strptime(payment_date, date_format)
        future_payment = date_obj + relativedelta(months=1)
        payment_date = future_payment.strftime(date_format)

    return JsonResponse({"msg": "Pagamento incluso com sucesso"})


@require_GET
@validate_user("financial")
def get_payments_month(request, user):
    date_referrer = datetime.now().date()
    date_start = date_referrer.replace(day=1)
    date_end = date_referrer + relativedelta(months=1, day=1)

    filters = {
        "begin": date_start,
        "end": date_end,
    }

    invoices_query = """
        SELECT
            fi.id,
            fi.name,
            SUM(
                CASE
                    fp.type
                    WHEN 0 THEN fp.value
                    ELSE 0
                END
            ) AS total_value_credit,
            SUM(
                CASE
                    fp.type
                    WHEN 1 THEN fp.value
                    ELSE 0
                END
            ) AS total_value_debit,
            SUM(
                CASE
                    fp.status
                    WHEN 0 THEN fp.value
                    ELSE 0
                END
            ) AS total_value_open,
            SUM(
                CASE
                    fp.status
                    WHEN 1 THEN fp.value
                    ELSE 0
                END
            ) AS total_value_closed,
            COUNT(*) AS total_payments
        FROM
            financial_invoice fi
            INNER JOIN financial_payment fp ON (fi.id = fp.invoice_id)
        WHERE
            (
                0 = 0
                AND fi.user_id = %(user_id)s
                AND fp.payment_date BETWEEN %(begin)s AND %(end)s
                AND fp.active = true
            )
        GROUP BY
            fi.id,
            fi.name
        ORDER BY
            fi.id;
    """

    with connection.cursor() as cursor:
        cursor.execute(invoices_query, {**filters, "user_id": user.id})
        invoices = cursor.fetchall()

    payments = [
        {
            "id": invoice[0],
            "name": invoice[1],
            "total_value_credit": float(invoice[2] or 0),
            "total_value_debit": float(invoice[3] or 0),
            "total_value_open": float(invoice[4] or 0),
            "total_value_closed": float(invoice[5] or 0),
            "total_payments": invoice[6],
        }
        for invoice in invoices
    ]

    return JsonResponse({"data": payments})


@require_GET
@validate_user("financial")
def detail_view(request, id, user):
    data = Payment.objects.filter(id=id, user=user).first()

    if data is None:
        return JsonResponse({"msg": "Payment not found"}, status=404)

    payment = {
        "id": data.id,
        "status": data.status,
        "type": data.type,
        "name": data.name,
        "date": data.date,
        "installments": data.installments,
        "payment_date": data.payment_date,
        "fixed": data.fixed,
        "active": data.active,
        "value": float(data.value or 0),
        "invoice": data.invoice.id,
        "invoice_name": data.invoice.name,
    }

    return JsonResponse({"data": payment})


@require_POST
@validate_user("financial")
def save_detail_view(request, id, user):
    data = json.loads(request.body)
    payment = Payment.objects.filter(id=id, user=user).first()

    if data is None or payment is None:
        return JsonResponse({"msg": "Payment not found"}, status=404)

    if payment.status == Payment.STATUS_DONE:
        return JsonResponse({"msg": "Pagamento ja foi baixado"}, status=500)

    if data.get("type"):
        payment.type = data.get("type")
    if data.get("name"):
        payment.name = data.get("name")
    if data.get("payment_date"):
        payment.payment_date = data.get("payment_date")
    if data.get("fixed") is not None:
        payment.fixed = data.get("fixed")
    if data.get("active") is not None:
        payment.active = data.get("active")
    if data.get("value"):
        old_value = payment.value
        new_value = data.get("value")

        invoice_value = float(payment.invoice.value_open - old_value) + new_value
        payment.invoice.value_open = invoice_value
        payment.invoice.save()

        payment.value = new_value

    payment.save()

    return JsonResponse({"msg": "Pagamento atualizado com sucesso"})


@require_POST
@validate_user("financial")
def payoff_detail_view(request, id, user):
    payment = Payment.objects.filter(id=id, user=user).first()

    if payment is None:
        return JsonResponse({"msg": "Pagamento não encontrado"}, status=400)

    if payment.status == 1:
        return JsonResponse({"msg": "Pagamento ja baixado"}, status=400)

    date_format = "%Y-%m-%d"

    if payment.invoice.fixed is True:
        future_payment = payment.payment_date + relativedelta(months=1)
        payment_date = future_payment.strftime(date_format)
        new_invoice = Invoice(
            type=payment.type,
            name=payment.name,
            date=payment.date,
            installments=payment.installments,
            payment_date=payment_date,
            fixed=payment.fixed,
            value=payment.value,
            value_open=payment.value,
            user=user,
        )
        new_invoice.save()
        tags = [tag.id for tag in payment.invoice.tags.all()]
        new_invoice.tags.set(tags)
        generate_payments(new_invoice)

    payment.status = Payment.STATUS_DONE
    payment.save()

    payment.invoice.value_open = (payment.invoice.value_open or 0) - payment.value
    payment.invoice.value_closed = (payment.invoice.value_closed or 0) + payment.value
    payment.invoice.save()

    return JsonResponse({"msg": "Pagamento baixado"})


@require_GET
@validate_user("financial")
def get_all_scheduled_view(request, user):
    req = request.GET
    filters = {}

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
        }
        for payment in data.get("data")
    ]

    data["page_size"] = page_size
    data["data"] = payments

    return JsonResponse({"data": data})
