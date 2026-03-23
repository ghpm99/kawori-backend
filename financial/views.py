import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import connection, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from contract.models import Contract
from financial.application.use_cases.get_metrics import GetMetricsUseCase
from financial.application.use_cases.report_ai_insights import ReportAIInsightsUseCase
from financial.application.use_cases.report_amount_invoice_by_tag import (
    ReportAmountInvoiceByTagUseCase,
)
from financial.application.use_cases.report_amount_payment import (
    ReportAmountPaymentUseCase,
)
from financial.application.use_cases.report_amount_payment_closed import (
    ReportAmountPaymentClosedUseCase,
)
from financial.application.use_cases.report_amount_payment_open import (
    ReportAmountPaymentOpenUseCase,
)
from financial.application.use_cases.report_balance_projection import (
    ReportBalanceProjectionUseCase,
)
from financial.application.use_cases.report_count_payment import (
    ReportCountPaymentUseCase,
)
from financial.application.use_cases.report_daily_cash_flow import (
    ReportDailyCashFlowUseCase,
)
from financial.application.use_cases.report_forecast_amount_value import (
    ReportForecastAmountValueUseCase,
)
from financial.application.use_cases.report_overdue_health import (
    ReportOverdueHealthUseCase,
)
from financial.application.use_cases.report_payment_summary import (
    ReportPaymentSummaryUseCase,
)
from financial.application.use_cases.report_tag_evolution import (
    ReportTagEvolutionUseCase,
)
from financial.application.use_cases.report_top_expenses import ReportTopExpensesUseCase
from financial.interfaces.api.serializers.report_ai_insights_serializers import (
    ReportAIInsightsPayloadSerializer,
    ReportAIInsightsResponseSerializer,
)
from financial.interfaces.api.serializers.report_payment_serializers import (
    ReportAmountPaymentOpenResponseSerializer,
    ReportAmountPaymentClosedResponseSerializer,
    ReportAmountInvoiceByTagResponseSerializer,
    ReportForecastAmountValueResponseSerializer,
    ReportMetricsResponseSerializer,
    ReportDailyCashFlowResponseSerializer,
    DateFromRequiredQuerySerializer,
    ReportAmountPaymentResponseSerializer,
    ReportCountPaymentResponseSerializer,
    ReportPaymentPeriodQuerySerializer,
    ReportPaymentSummaryResponseSerializer,
    RequiredPeriodQuerySerializer,
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
    response_serializer = ReportAIInsightsResponseSerializer(result)
    return JsonResponse(response_serializer.data)


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

    response_serializer = ReportPaymentSummaryResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


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
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportCountPaymentUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportCountPaymentResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_amount_payment_view(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportAmountPaymentUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportAmountPaymentResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_amount_payment_open_view(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportAmountPaymentOpenUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportAmountPaymentOpenResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_amount_payment_closed_view(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportAmountPaymentClosedUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportAmountPaymentClosedResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_amount_invoice_by_tag_view(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    tags = ReportAmountInvoiceByTagUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportAmountInvoiceByTagResponseSerializer({"data": tags})
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_forecast_amount_value(request, user):
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = ReportForecastAmountValueUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        cursor_factory=connection.cursor,
    )

    response_serializer = ReportForecastAmountValueResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


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
    serializer = ReportPaymentPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    data = GetMetricsUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        get_total_payment_fn=get_total_payment,
        get_total_payment_from_date_fn=get_total_payment_from_date,
    )

    response_serializer = ReportMetricsResponseSerializer(data)
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_daily_cash_flow_view(request, user):
    serializer = RequiredPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    payload = ReportDailyCashFlowUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
    )
    response_serializer = ReportDailyCashFlowResponseSerializer(payload)
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def report_top_expenses_view(request, user):
    serializer = RequiredPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    limit = parse_int_query_param(request.GET.get("limit"), default=10, minimum=1)
    data = ReportTopExpensesUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        limit=limit,
        payment_status_to_label_fn=payment_status_to_label,
    )

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def report_balance_projection_view(request, user):
    serializer = DateFromRequiredQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    months_ahead = parse_int_query_param(
        request.GET.get("months_ahead"), default=6, minimum=1
    )

    return JsonResponse(
        ReportBalanceProjectionUseCase().execute(
            user=user,
            start_date=serializer.validated_data["date_from_parsed"],
            months_ahead=months_ahead,
        )
    )


@require_GET
@validate_user("financial")
def report_overdue_health_view(request, user):
    serializer = RequiredPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    return JsonResponse(
        ReportOverdueHealthUseCase().execute(
            user=user,
            date_from=serializer.validated_data["date_from_parsed"],
            date_to=serializer.validated_data["date_to_parsed"],
        )
    )


@require_GET
@validate_user("financial")
def report_tag_evolution_view(request, user):
    serializer = RequiredPeriodQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=400,
        )

    compare_with_previous_period = True
    if request.GET.get("compare_with_previous_period") is not None:
        compare_with_previous_period = boolean(
            request.GET.get("compare_with_previous_period")
        )

    data = ReportTagEvolutionUseCase().execute(
        user=user,
        date_from=serializer.validated_data["date_from_parsed"],
        date_to=serializer.validated_data["date_to_parsed"],
        compare_with_previous_period=compare_with_previous_period,
    )

    return JsonResponse({"data": data})
