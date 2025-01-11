import json
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from financial.models import Invoice, Payment
from financial.utils import calculate_installments, generate_payments
from kawori.decorators import add_cors_react_dev, validate_super_user
from kawori.utils import boolean, format_date, paginate


@add_cors_react_dev
@validate_super_user
@require_GET
def get_all_view(request, user):
    req = request.GET
    filters = {}

    if req.get("status"):
        filters["status"] = req.get("status")
    if req.get("type"):
        filters["type"] = req.get("type")
    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")
    if req.get("date__gte"):
        filters["date__gte"] = format_date(req.get("date__gte")) or datetime(
            2018, 1, 1
        )
    if req.get("date__lte"):
        filters["date__lte"] = format_date(
            req.get("date__lte")
        ) or datetime.now() + timedelta(days=1)
    if req.get("installments"):
        filters["installments"] = req.get("installments")
    if req.get("payment_date__gte"):
        filters["payment_date__gte"] = format_date(
            req.get("payment_date__gte")
        ) or datetime(2018, 1, 1)
    if req.get("payment_date__lte"):
        filters["payment_date__lte"] = format_date(
            req.get("payment_date__lte")
        ) or datetime.now() + timedelta(days=1)
    if req.get("fixed"):
        filters["fixed"] = boolean(req.get("fixed"))
    if req.get("active"):
        filters["active"] = boolean(req.get("active"))
    if req.get("contract"):
        filters["invoice__contract__name__icontains"] = req.get("contract")

    payments_query = Payment.objects.filter(**filters, user=user).order_by(
        "payment_date"
    )

    data = paginate(payments_query, req.get("page"), req.get("page_size"))

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

    data["data"] = payments

    return JsonResponse({"data": data})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
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


@add_cors_react_dev
@validate_super_user
@require_GET
def get_payments_month(request, user):
    date_referrer = datetime.now().date()
    date_start = date_referrer.replace(day=1)
    date_end = date_referrer + relativedelta(months=1, day=1)

    filters = {
        "begin": date_start,
        "end": date_end,
    }

    contracts_query = """
        SELECT
            fc.id,
            fc.name,
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
            financial_contract AS fc
            INNER JOIN financial_invoice fi ON (fc.id = fi.contract_id)
            INNER JOIN financial_payment fp ON (fi.id = fp.invoice_id)
        WHERE
            (
                0 = 0
                AND fc.user_id = %(user_id)s
                AND fp.payment_date BETWEEN %(begin)s AND %(end)s
                AND fp.active = true
            )
        GROUP BY
            fc.id,
            fc.name
        ORDER BY
            fc.id;
    """

    with connection.cursor() as cursor:
        cursor.execute(contracts_query, {**filters, "user_id": user.id})
        contracts = cursor.fetchall()

    payments = [
        {
            "id": contract[0],
            "name": contract[1],
            "total_value_credit": float(contract[2] or 0),
            "total_value_debit": float(contract[3] or 0),
            "total_value_open": float(contract[4] or 0),
            "total_value_closed": float(contract[5] or 0),
            "total_payments": contract[6],
        }
        for contract in contracts
    ]

    return JsonResponse({"data": payments})


@add_cors_react_dev
@validate_super_user
@require_GET
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
        "contract": data.invoice.contract.id,
        "contract_name": data.invoice.contract.name,
    }

    return JsonResponse({"data": payment})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
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

        invoice_value = (
            float(payment.invoice.value_open - old_value) + new_value
        )
        payment.invoice.value_open = invoice_value
        payment.invoice.save()

        contract_value = (
            float(payment.invoice.contract.value_open - old_value) + new_value
        )
        payment.invoice.contract.value_open = contract_value
        payment.invoice.contract.save()

        payment.value = new_value

    payment.save()

    return JsonResponse({"msg": "ok"})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
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
            contract=payment.invoice.contract,
            user=user,
        )
        new_invoice.save()
        tags = [tag.id for tag in payment.invoice.tags.all()]
        new_invoice.tags.set(tags)
        generate_payments(new_invoice)

        new_invoice.contract.value_open = (
            new_invoice.contract.value_open or 0
        ) + new_invoice.value
        new_invoice.contract.value = (
            new_invoice.contract.value or 0
        ) + new_invoice.value
        new_invoice.contract.save()

    payment.status = Payment.STATUS_DONE
    payment.save()

    payment.invoice.value_open = (
        payment.invoice.value_open or 0
    ) - payment.value
    payment.invoice.value_closed = (
        payment.invoice.value_closed or 0
    ) + payment.value
    payment.invoice.save()

    payment.invoice.contract.value_open = (
        payment.invoice.contract.value_open or 0
    ) - payment.value
    payment.invoice.contract.value_closed = (
        payment.invoice.contract.value_closed or 0
    ) + payment.value
    payment.invoice.contract.save()

    return JsonResponse({"msg": "Pagamento baixado"})
