import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from contract.models import Contract
from financial.application.use_cases.report_ai_insights import (
    ReportAIInsightsUseCase,
)
from financial.application.use_cases.report_payment_summary import (
    ReportPaymentSummaryUseCase,
)
from financial.interfaces.api.serializers.report_ai_insights_serializers import (
    ReportAIInsightsPayloadSerializer,
)
from financial.interfaces.api.serializers.report_payment_serializers import (
    ReportPaymentPeriodQuerySerializer,
)
from financial.utils import (
    calculate_installments,
    generate_payments,
    update_contract_value,
)
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import Payment
from tag.models import Tag


@require_GET
@validate_user("financial")
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
        filters["date__gte"] = format_date(req.get("date__gte")) or datetime(2018, 1, 1)
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
    if req.get("invoice"):
        filters["invoice__name__icontains"] = req.get("invoice")

    if "active" not in filters:
        filters["active"] = True

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
            "invoice_id": payment.invoice.id,
            "invoice_name": payment.invoice.name,
        }
        for payment in data.get("data")
    ]

    data["data"] = payments

    return JsonResponse({"data": data})


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
                AND fi.active = true
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


@require_POST
@validate_user("financial")
def save_new_view(request, user):
    data = json.loads(request.body)

    installments = data.get("installments")
    payment_date = data.get("payment_date")

    value_installments = calculate_installments(data.get("value"), installments)

    date_format = "%Y-%m-%d"

    with transaction.atomic():
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
def detail_view(request, id, user):
    data = Payment.objects.filter(id=id, user=user, active=True).first()

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


@require_POST
@validate_user("financial")
def save_detail_view(request, id, user):
    data = json.loads(request.body)
    payment = Payment.objects.filter(id=id, user=user, active=True).first()

    if data is None or payment is None:
        return JsonResponse({"msg": "Payment not found"}, status=404)

    if payment.status == Payment.STATUS_DONE:
        return JsonResponse({"msg": "Pagamento ja foi baixado"}, status=500)

    with transaction.atomic():
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

            contract_value = (
                float(payment.invoice.contract.value_open - old_value) + new_value
            )
            payment.invoice.contract.value_open = contract_value
            payment.invoice.contract.save()

            payment.value = new_value

        payment.save()

    return JsonResponse({"msg": "ok"})


@require_POST
@validate_user("financial")
def payoff_detail_view(request, id, user):
    payment = Payment.objects.filter(id=id, user=user, active=True).first()

    if payment is None:
        return JsonResponse({"msg": "Pagamento não encontrado"}, status=400)

    if payment.status == 1:
        return JsonResponse({"msg": "Pagamento ja baixado"}, status=400)

    with transaction.atomic():
        if payment.invoice.fixed is True:
            payment_date = payment.payment_date + relativedelta(months=1)
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

        payment.invoice.value_open = (payment.invoice.value_open or 0) - payment.value
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


def parse_period_filters(request, default_begin=None, default_end=None, required=False):
    date_from = (
        format_date(request.GET.get("date_from"))
        if request.GET.get("date_from")
        else None
    )
    date_to = (
        format_date(request.GET.get("date_to")) if request.GET.get("date_to") else None
    )

    if required and (date_from is None or date_to is None):
        return None, JsonResponse(
            {"msg": "date_from and date_to are required"}, status=400
        )

    begin = date_from or default_begin
    end = date_to or default_end

    if begin is None or end is None:
        return None, JsonResponse({"msg": "Invalid period"}, status=400)

    if begin > end:
        return None, JsonResponse(
            {"msg": "date_from must be less than or equal to date_to"}, status=400
        )

    return {"begin": begin, "end": end}, None


def parse_int_query_param(value, default, minimum=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < minimum:
        return default

    return parsed


def payment_status_to_label(status):
    return "closed" if status == Payment.STATUS_DONE else "open"


def parse_optional_period_filters(request):
    date_from = (
        format_date(request.GET.get("date_from"))
        if request.GET.get("date_from")
        else None
    )
    date_to = (
        format_date(request.GET.get("date_to")) if request.GET.get("date_to") else None
    )

    if date_from and date_to and date_from > date_to:
        return None, JsonResponse(
            {"msg": "date_from must be less than or equal to date_to"}, status=400
        )

    return {"begin": date_from, "end": date_to}, None


@require_POST
@validate_user("financial")
def report_ai_insights_view(request, user):
    try:
        payload = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=400)

    serializer = ReportAIInsightsPayloadSerializer(data=payload)
    if not serializer.is_valid():
        return JsonResponse({"msg": "JSON inválido"}, status=400)

    result = ReportAIInsightsUseCase().execute(
        user=user, payload=serializer.validated_data
    )
    return JsonResponse(result)


@require_GET
@validate_user("financial")
def report_payment_view(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportPaymentSummaryUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def get_all_contract_view(request, user):
    req = request.GET
    filters = {}

    if req.get("id"):
        filters["id"] = req.get("id")

    contracts_query = Contract.objects.filter(**filters, user=user).order_by("id")

    data = paginate(contracts_query, req.get("page"), req.get("page_size"))

    contracts = [
        {
            "id": contract.id,
            "name": contract.name,
            "value": float(contract.value or 0),
            "value_open": float(contract.value_open or 0),
            "value_closed": float(contract.value_closed or 0),
        }
        for contract in data.get("data")
    ]

    data["data"] = contracts

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def get_all_invoice_view(request, user):
    req = request.GET
    filters = {}

    if req.get("status"):
        filters["status"] = req.get("status")
    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")
    if req.get("installments"):
        filters["installments"] = req.get("installments")
    if req.get("date__gte"):
        filters["date__gte"] = format_date(req.get("date__gte")) or datetime(2018, 1, 1)
    if req.get("date__lte"):
        filters["date__lte"] = format_date(
            req.get("date__lte")
        ) or datetime.now() + timedelta(days=1)

    invoices_query = Invoice.objects.filter(**filters, user=user, active=True).order_by(
        "id"
    )

    data = paginate(invoices_query, req.get("page"), req.get("page_size"))

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
            "contract": invoice.contract.id,
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in invoice.tags.all()
            ],
        }
        for invoice in data.get("data")
    ]

    data["data"] = invoices

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
def save_new_contract_view(request, user):
    data = json.loads(request.body)
    contract = Contract(name=data.get("name"), user=user)
    contract.save()

    return JsonResponse({"msg": "Contrato incluso com sucesso"})


@require_GET
@validate_user("financial")
def detail_contract_view(request, id, user):
    data = Contract.objects.filter(id=id, user=user).first()

    if data is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)

    contract = {
        "id": data.id,
        "name": data.name,
        "value": float(data.value or 0),
        "value_open": float(data.value_open or 0),
        "value_closed": float(data.value_closed or 0),
    }

    return JsonResponse({"data": contract})


@require_GET
@validate_user("financial")
def detail_contract_invoices_view(request, id, user):
    req = request.GET

    invoices_query = Invoice.objects.filter(
        contract=id, user=user, active=True
    ).order_by("id")

    data = paginate(invoices_query, req.get("page"), req.get("page_size"))

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
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in invoice.tags.all()
            ],
        }
        for invoice in data.get("data")
    ]

    data["data"] = invoices

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
def include_new_invoice_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)

    if data.get("tags"):
        tag_ids = data.get("tags")
        tags = Tag.objects.filter(id__in=tag_ids, user=user)
        if tags.count() != len(set(tag_ids)):
            return JsonResponse(
                {"msg": "Uma ou mais tags não pertencem ao usuário"}, status=400
            )

    with transaction.atomic():
        invoice = Invoice(
            status=data.get("status"),
            type=data.get("type"),
            name=data.get("name"),
            date=data.get("date"),
            installments=data.get("installments"),
            payment_date=data.get("payment_date"),
            fixed=data.get("fixed"),
            active=data.get("active"),
            value=data.get("value"),
            value_open=data.get("value"),
            contract=contract,
            user=user,
        )
        invoice.save()
        if data.get("tags"):
            invoice.tags.set(tags)

        generate_payments(invoice)

        contract.value_open = float(contract.value_open or 0) + float(invoice.value)
        contract.value = float(contract.value or 0) + float(invoice.value)
        contract.save()

    return JsonResponse({"msg": "Nota inclusa com sucesso"})


@require_GET
@validate_user("financial")
def detail_invoice_view(request, id, user):
    invoice = Invoice.objects.filter(id=id, user=user, active=True).first()

    if invoice is None:
        return JsonResponse({"msg": "Invoice not found"}, status=404)

    tags = [
        {"id": tag.id, "name": tag.name, "color": tag.color}
        for tag in invoice.tags.all()
    ]

    invoice = {
        "id": invoice.id,
        "status": invoice.status,
        "name": invoice.name,
        "installments": invoice.installments,
        "value": float(invoice.value or 0),
        "value_open": float(invoice.value_open or 0),
        "value_closed": float(invoice.value_closed or 0),
        "date": invoice.date,
        "contract": invoice.contract.id,
        "contract_name": invoice.contract.name,
        "tags": tags,
    }

    return JsonResponse({"data": invoice})


@require_GET
@validate_user("financial")
def detail_invoice_payments_view(request, id, user):
    req = request.GET
    payments_query = Payment.objects.filter(
        invoice=id, user=user, active=True
    ).order_by("id")

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
        }
        for payment in data.get("data")
    ]

    data["data"] = payments

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
def merge_contract_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)
    contracts = data.get("contracts") or []

    with transaction.atomic():
        for contract_id in contracts:
            if contract_id == contract.id:
                continue
            invoices = Invoice.objects.filter(
                contract=contract_id, user=user, active=True
            ).all()
            for invoice in invoices:
                invoice.contract = contract
                invoice.save()
            Contract.objects.filter(id=contract_id, user=user).delete()

        update_contract_value(contract)

    return JsonResponse({"msg": "Contratos mesclados com sucesso!"})


@require_GET
@validate_user("financial")
def get_all_tag_view(request, user):
    req = request.GET
    filters = {}

    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")

    datas = Tag.objects.filter(**filters, user=user).all().order_by("name")

    tags = [{"id": data.id, "name": data.name, "color": data.color} for data in datas]

    return JsonResponse({"data": tags})


@require_POST
@validate_user("financial")
def include_new_tag_view(request, user):
    data = json.loads(request.body)

    tag = Tag(name=data.get("name"), color=data.get("color"), user=user)

    tag.save()

    return JsonResponse({"msg": "Tag inclusa com sucesso"})


@require_POST
@validate_user("financial")
def save_tag_invoice_view(request, id, user):
    data = json.loads(request.body)

    if data is None:
        return JsonResponse({"msg": "Tags not found"}, status=404)

    invoice = Invoice.objects.filter(id=id, user=user).first()
    if invoice is None:
        return JsonResponse({"msg": "Invoice not found"}, status=404)

    tags = Tag.objects.filter(id__in=data, user=user)
    if tags.count() != len(set(data)):
        return JsonResponse(
            {"msg": "Uma ou mais tags não pertencem ao usuário"}, status=400
        )

    with transaction.atomic():
        invoice.tags.set(tags)
        invoice.save()

    return JsonResponse({"msg": "ok"})


@require_GET
@validate_user("financial")
def report_count_payment_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id}
    if params["begin"] and params["end"]:
        query_params.update({"begin": params["begin"], "end": params["end"]})
        count_payment = """
            SELECT
                COALESCE(COUNT(id), 0) as payment_total
            FROM
                financial_payment fp
            WHERE
                user_id=%(user_id)s
                AND active=true
                AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
        """
    else:
        count_payment = """
            SELECT
                COALESCE(COUNT(id), 0) as payment_total
            FROM
                financial_payment fp
            WHERE
                user_id=%(user_id)s
                AND active=true;
        """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, query_params)
        payment_total = cursor.fetchone()

    return JsonResponse({"data": int(payment_total[0])})


@require_GET
@validate_user("financial")
def report_amount_payment_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id}
    if params["begin"] and params["end"]:
        query_params.update({"begin": params["begin"], "end": params["end"]})
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.active=true
                AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
        """
    else:
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.active=true;
        """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, query_params)
        amount_payment_total = cursor.fetchone()

    return JsonResponse({"data": float(amount_payment_total[0])})


@require_GET
@validate_user("financial")
def report_amount_payment_open_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id}
    if params["begin"] and params["end"]:
        query_params.update({"begin": params["begin"], "end": params["end"]})
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.status=0
                AND fp.active=true
                AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
        """
    else:
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.status=0
                AND fp.active=true;
        """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, query_params)
        amount_payment_total = cursor.fetchone()

    return JsonResponse({"data": float(amount_payment_total[0])})


@require_GET
@validate_user("financial")
def report_amount_payment_closed_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id}
    if params["begin"] and params["end"]:
        query_params.update({"begin": params["begin"], "end": params["end"]})
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.status=1
                AND fp.active=true
                AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
        """
    else:
        count_payment = """
            SELECT
                COALESCE(SUM(value), 0) as amount_payment_total
            FROM
                financial_payment fp
            WHERE
                fp.user_id=%(user_id)s
                AND fp.status=1
                AND fp.active=true;
        """

    with connection.cursor() as cursor:
        cursor.execute(count_payment, query_params)
        amount_payment_total = cursor.fetchone()

    return JsonResponse({"data": float(amount_payment_total[0])})


@require_GET
@validate_user("financial")
def report_amount_invoice_by_tag_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id, "payment_type": Payment.TYPE_DEBIT}
    if params["begin"] and params["end"]:
        query_params.update({"begin": params["begin"], "end": params["end"]})
        amount_invoice = """
            SELECT
                ft.id,
                ft."name",
                COALESCE(ft.color, '#000'),
                sum(fp.value)
            FROM
                financial_tag ft
            INNER JOIN financial_invoice_tags fit ON
                ft.id = fit.tag_id
            INNER JOIN financial_invoice fi ON
                fit.invoice_id = fi.id
            INNER JOIN financial_payment fp ON
                fp.invoice_id = fi.id
            WHERE
                ft.user_id=%(user_id)s
                AND fp.type=%(payment_type)s
                AND fp."payment_date" BETWEEN %(begin)s AND %(end)s
                AND fi.active=true
                AND fp.active=true
            GROUP BY
                ft.id
            ORDER BY
                sum(fp.value) DESC;
        """
    else:
        amount_invoice = """
            SELECT
                ft.id,
                ft."name",
                COALESCE(ft.color, '#000'),
                sum(fp.value)
            FROM
                financial_tag ft
            INNER JOIN financial_invoice_tags fit ON
                ft.id = fit.tag_id
            INNER JOIN financial_invoice fi ON
                fit.invoice_id = fi.id
            INNER JOIN financial_payment fp ON
                fp.invoice_id = fi.id
            WHERE
                ft.user_id=%(user_id)s
                AND fp.type=%(payment_type)s
                AND fi.active=true
                AND fp.active=true
            GROUP BY
                ft.id
            ORDER BY
                sum(fp.value) DESC;
        """
    with connection.cursor() as cursor:
        cursor.execute(amount_invoice, query_params)
        amount_invoice = cursor.fetchall()

    tags = [
        {"id": data[0], "name": data[1], "color": data[2], "amount": float(data[3])}
        for data in amount_invoice
    ]

    return JsonResponse({"data": tags})


@require_GET
@validate_user("financial")
def report_forecast_amount_value(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    query_params = {"user_id": user.id}

    query_monthly_avg = """
        SELECT
            AVG(monthly_total) AS avg_monthly,
            COUNT(*) AS total_months
        FROM (
            SELECT
                date_trunc('month', fp.payment_date) AS month,
                SUM(fp.value) AS monthly_total
            FROM
                financial_payment fp
            WHERE 1=1
                AND fp.user_id = %(user_id)s
                AND fp.active = true
            GROUP BY
                date_trunc('month', fp.payment_date)
        ) monthly_totals;
    """

    with connection.cursor() as cursor:
        cursor.execute(query_monthly_avg, query_params)
        result = cursor.fetchone()

    avg_monthly = float(result[0] or 0)
    total_months = int(result[1] or 0)

    if avg_monthly == 0:
        return JsonResponse({"data": 0})

    if params["begin"] and params["end"]:
        months_in_period = (
            (params["end"].year - params["begin"].year) * 12
            + params["end"].month
            - params["begin"].month
            + 1
        )
    else:
        months_in_period = total_months

    forecast_value = round(avg_monthly * months_in_period, 2)

    return JsonResponse({"data": forecast_value})


def get_total_payment_from_date(date_begin, date_end, user_id, type):

    sum_payment_value = """
        SELECT
            COALESCE(SUM(value), 0) as total_payment
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=%(type)s
            AND fp.active=true
            AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            sum_payment_value,
            {"begin": date_begin, "end": date_end, "type": type, "user_id": user_id},
        )
        total_payment_current = float(cursor.fetchone()[0])

    period_days = (date_end - date_begin).days + 1
    prev_end = date_begin - timedelta(days=1)
    prev_begin = prev_end - timedelta(days=period_days - 1)

    with connection.cursor() as cursor:
        cursor.execute(
            sum_payment_value,
            {"begin": prev_begin, "end": prev_end, "type": type, "user_id": user_id},
        )
        total_payment_last_period = float(cursor.fetchone()[0])

    return (total_payment_current, total_payment_last_period)


def get_total_payment(user_id, type):

    sum_payment_value = """
        SELECT
            COALESCE(SUM(value), 0) as total_payment
        FROM
            financial_payment fp
        WHERE 1=1
            AND fp.user_id=%(user_id)s
            AND fp.type=%(type)s
            AND fp.active=true;
    """

    with connection.cursor() as cursor:
        cursor.execute(sum_payment_value, {"type": type, "user_id": user_id})
        return float(cursor.fetchone()[0])


@require_GET
@validate_user("financial")
def get_metrics_view(request, user):
    params, error_response = parse_optional_period_filters(request)
    if error_response:
        return error_response

    def percent_change(current, previous):
        if previous == 0:
            return 0
        return round(((current - previous) / abs(previous)) * 100, 2)

    if params["begin"] and params["end"]:
        begin = params["begin"]
        end = params["end"]
        revenues_current, revenues_last_month = get_total_payment_from_date(
            begin, end, user.id, Payment.TYPE_CREDIT
        )
        expenses_current, expenses_last_month = get_total_payment_from_date(
            begin, end, user.id, Payment.TYPE_DEBIT
        )
    else:
        revenues_current = get_total_payment(user.id, Payment.TYPE_CREDIT)
        expenses_current = get_total_payment(user.id, Payment.TYPE_DEBIT)
        revenues_last_month = 0
        expenses_last_month = 0

    revenue_data = {
        "value": revenues_current,
        "metric_value": percent_change(revenues_current, revenues_last_month),
    }

    expenses_data = {
        "value": expenses_current,
        "metric_value": percent_change(expenses_current, expenses_last_month),
    }

    profit_current = revenues_current - expenses_current
    profit_last_month = revenues_last_month - expenses_last_month

    profit_data = {
        "value": profit_current,
        "metric_value": percent_change(profit_current, profit_last_month),
    }

    growth_data = {"value": percent_change(profit_current, profit_last_month)}

    data = {
        "revenues": revenue_data,
        "expenses": expenses_data,
        "profit": profit_data,
        "growth": growth_data,
    }

    return JsonResponse(data)


@require_GET
@validate_user("financial")
def report_daily_cash_flow_view(request, user):
    filters, error_response = parse_period_filters(request, required=True)
    if error_response:
        return error_response

    grouped = (
        Payment.objects.filter(
            user=user,
            active=True,
            payment_date__range=(filters["begin"], filters["end"]),
        )
        .values("payment_date")
        .annotate(
            credit=Coalesce(
                Sum("value", filter=Q(type=Payment.TYPE_CREDIT)), Decimal("0")
            ),
            debit=Coalesce(
                Sum("value", filter=Q(type=Payment.TYPE_DEBIT)), Decimal("0")
            ),
        )
        .order_by("payment_date")
    )

    by_date = {row["payment_date"]: row for row in grouped}
    cursor = filters["begin"]
    accumulated = 0.0
    data = []
    total_credit = 0.0
    total_debit = 0.0

    while cursor <= filters["end"]:
        row = by_date.get(cursor)
        credit = float((row or {}).get("credit") or 0)
        debit = float((row or {}).get("debit") or 0)
        net = credit - debit
        accumulated += net
        total_credit += credit
        total_debit += debit

        data.append(
            {
                "date": cursor,
                "credit": credit,
                "debit": debit,
                "net": net,
                "accumulated": accumulated,
            }
        )
        cursor += timedelta(days=1)

    return JsonResponse(
        {
            "data": data,
            "summary": {
                "total_credit": total_credit,
                "total_debit": total_debit,
                "net": total_credit - total_debit,
            },
        }
    )


@require_GET
@validate_user("financial")
def report_top_expenses_view(request, user):
    filters, error_response = parse_period_filters(request, required=True)
    if error_response:
        return error_response

    limit = parse_int_query_param(request.GET.get("limit"), default=10, minimum=1)

    payments = (
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(filters["begin"], filters["end"]),
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
                "status": payment_status_to_label(payment.status),
            }
        )

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def report_balance_projection_view(request, user):
    start_date = (
        format_date(request.GET.get("date_from"))
        if request.GET.get("date_from")
        else None
    )
    if start_date is None:
        return JsonResponse({"msg": "date_from is required"}, status=400)

    months_ahead = parse_int_query_param(
        request.GET.get("months_ahead"), default=6, minimum=1
    )

    start_month = start_date.replace(day=1)
    data = []

    for i in range(months_ahead):
        month_start = start_month + relativedelta(months=i)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

        sums = Payment.objects.filter(
            user=user,
            active=True,
            payment_date__range=(month_start, month_end),
        ).aggregate(
            credit=Coalesce(
                Sum("value", filter=Q(type=Payment.TYPE_CREDIT)), Decimal("0")
            ),
            debit=Coalesce(
                Sum("value", filter=Q(type=Payment.TYPE_DEBIT)), Decimal("0")
            ),
        )

        projected_credit = float(sums["credit"] or 0)
        projected_debit = float(sums["debit"] or 0)
        projected_balance = projected_credit - projected_debit

        if projected_balance < 0:
            risk_level = "high"
        elif projected_credit > 0 and (projected_balance / projected_credit) < 0.1:
            risk_level = "medium"
        else:
            risk_level = "low"

        data.append(
            {
                "month": month_start.strftime("%Y-%m"),
                "projected_credit": projected_credit,
                "projected_debit": projected_debit,
                "projected_balance": projected_balance,
                "risk_level": risk_level,
            }
        )

    return JsonResponse(
        {
            "data": data,
            "assumptions": {
                "includes_open_payments": True,
                "includes_fixed_entries": True,
            },
        }
    )


@require_GET
@validate_user("financial")
def report_overdue_health_view(request, user):
    filters, error_response = parse_period_filters(request, required=True)
    if error_response:
        return error_response

    today = date.today()

    overdue_payments = (
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            status=Payment.STATUS_OPEN,
            payment_date__range=(filters["begin"], filters["end"]),
            payment_date__lt=today,
        )
        .select_related("invoice")
        .prefetch_related("invoice__tags")
    )

    overdue_count = overdue_payments.count()
    overdue_amount = float(
        overdue_payments.aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
        or 0
    )

    delays = [(today - payment.payment_date).days for payment in overdue_payments]
    average_delay_days = round((sum(delays) / len(delays)), 1) if delays else 0

    total_period_amount = float(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(filters["begin"], filters["end"]),
        ).aggregate(total=Coalesce(Sum("value"), Decimal("0")))["total"]
        or 0
    )
    overdue_ratio = (
        round((overdue_amount / total_period_amount) * 100, 1)
        if total_period_amount
        else 0
    )

    critical_map = defaultdict(
        lambda: {"category": "", "amount": 0.0, "payment_ids": set()}
    )
    for payment in overdue_payments:
        for tag in payment.invoice.tags.all():
            item = critical_map[tag.id]
            item["category"] = tag.name
            item["amount"] += float(payment.value or 0)
            item["payment_ids"].add(payment.id)

    critical_categories = sorted(
        (
            {
                "category": item["category"],
                "amount": item["amount"],
                "count": len(item["payment_ids"]),
            }
            for item in critical_map.values()
        ),
        key=lambda value: value["amount"],
        reverse=True,
    )[:3]

    return JsonResponse(
        {
            "data": {
                "overdue_count": overdue_count,
                "overdue_amount": overdue_amount,
                "average_delay_days": average_delay_days,
                "overdue_ratio": overdue_ratio,
                "critical_categories": critical_categories,
            }
        }
    )


@require_GET
@validate_user("financial")
def report_tag_evolution_view(request, user):
    filters, error_response = parse_period_filters(request, required=True)
    if error_response:
        return error_response

    compare_with_previous_period = True
    if request.GET.get("compare_with_previous_period") is not None:
        compare_with_previous_period = boolean(
            request.GET.get("compare_with_previous_period")
        )

    current_rows = (
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            payment_date__range=(filters["begin"], filters["end"]),
            invoice__tags__isnull=False,
        )
        .values("invoice__tags__id", "invoice__tags__name")
        .annotate(amount=Coalesce(Sum("value"), Decimal("0")))
    )

    current_data = {
        row["invoice__tags__id"]: {
            "tag_id": row["invoice__tags__id"],
            "tag_name": row["invoice__tags__name"],
            "current_amount": float(row["amount"] or 0),
        }
        for row in current_rows
    }

    previous_data = {}
    if compare_with_previous_period:
        period_days = (filters["end"] - filters["begin"]).days + 1
        previous_end = filters["begin"] - timedelta(days=1)
        previous_begin = previous_end - timedelta(days=period_days - 1)

        previous_rows = (
            Payment.objects.filter(
                user=user,
                active=True,
                type=Payment.TYPE_DEBIT,
                payment_date__range=(previous_begin, previous_end),
                invoice__tags__isnull=False,
            )
            .values("invoice__tags__id")
            .annotate(amount=Coalesce(Sum("value"), Decimal("0")))
        )
        previous_data = {
            row["invoice__tags__id"]: float(row["amount"] or 0) for row in previous_rows
        }

    data = []
    for item in current_data.values():
        previous_amount = previous_data.get(item["tag_id"], 0.0)
        if previous_amount == 0:
            variation_percent = 100.0 if item["current_amount"] > 0 else 0.0
        else:
            variation_percent = (
                (item["current_amount"] - previous_amount) / abs(previous_amount)
            ) * 100

        data.append(
            {
                "tag_id": item["tag_id"],
                "tag_name": item["tag_name"],
                "current_amount": item["current_amount"],
                "previous_amount": (
                    previous_amount if compare_with_previous_period else 0.0
                ),
                "variation_percent": (
                    round(variation_percent, 1) if compare_with_previous_period else 0.0
                ),
            }
        )

    data.sort(key=lambda item: item["current_amount"], reverse=True)

    return JsonResponse({"data": data})
