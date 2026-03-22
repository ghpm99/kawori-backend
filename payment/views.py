import json
from datetime import datetime, timedelta
from http import HTTPStatus
from math import ceil
from typing import List

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Case, Count, DecimalField, Q, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from financial.utils import calculate_installments, generate_payments
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.application.use_cases.csv_ai_map import CSVAIMapUseCase
from payment.application.use_cases.csv_ai_normalize import CSVAINormalizeUseCase
from payment.application.use_cases.csv_ai_reconcile import CSVAIReconcileUseCase
from payment.application.use_cases.csv_ai_tag_suggestions import (
    CSVAITagSuggestionsUseCase,
)
from payment.application.use_cases.csv_import import CSVImportUseCase
from payment.application.use_cases.csv_resolve_imports import (
    CSVResolveImportsUseCase,
)
from payment.application.use_cases.get_csv_mapping import GetCSVMappingUseCase
from payment.application.use_cases.process_csv_upload import ProcessCSVUploadUseCase
from payment.application.use_cases.statement_anomalies import (
    StatementAnomaliesUseCase,
)
from payment.interfaces.api.serializers.csv_ai_serializers import (
    CSVAIMapInputSerializer,
    CSVAINormalizeInputSerializer,
    CSVAIReconcileInputSerializer,
    CSVAITagSuggestionsInputSerializer,
)
from payment.interfaces.api.serializers.csv_import_serializers import (
    CSVImportInputSerializer,
    CSVResolveImportsInputSerializer,
    ProcessCSVUploadInputSerializer,
)
from payment.interfaces.api.serializers.csv_mapping_serializers import (
    CSVMappingInputSerializer,
)
from payment.interfaces.api.serializers.statement_serializers import (
    StatementAnomaliesQuerySerializer,
)
from payment.models import ImportedPayment, Payment
from payment.utils import CSVMapping, PaymentImport, Row

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
    if req.get("invoice_id"):
        filters["invoice_id"] = req.get("invoice_id")
    if req.get("invoice"):
        filters["invoice__name__icontains"] = req.get("invoice")

    payments_query = Payment.objects.filter(**filters, user=user).order_by(
        "payment_date", "id"
    )
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

    return JsonResponse({"data": data})


@require_POST
@validate_user("financial")
@audit_log("payment.create", CATEGORY_FINANCIAL, "Payment")
def save_new_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    installments = data.get("installments")
    payment_date = data.get("payment_date")

    value = data.get("value")
    if isinstance(value, str):
        value = float(value)

    if installments is None:
        return JsonResponse(
            {"msg": "Erro ao incluir pagamento"},
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    if installments <= 0:
        return JsonResponse({"msg": "Pagamento incluso com sucesso"})

    value_installments = calculate_installments(value, installments)

    date_format = "%Y-%m-%d"

    try:
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
    except Exception:
        return JsonResponse(
            {"msg": "Erro ao incluir pagamento"},
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    return JsonResponse({"msg": "Pagamento incluso com sucesso"})


@require_GET
@validate_user("financial")
def get_payments_month(request, user):
    date_from = (
        format_date(request.GET.get("date_from"))
        if request.GET.get("date_from")
        else None
    )
    date_to = (
        format_date(request.GET.get("date_to")) if request.GET.get("date_to") else None
    )

    if date_from and date_to and date_from > date_to:
        return JsonResponse(
            {"msg": "date_from must be less than or equal to date_to"}, status=400
        )

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

    return JsonResponse({"data": payments})


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
    }

    return JsonResponse({"data": payment})


@require_POST
@validate_user("financial")
@audit_log("payment.update", CATEGORY_FINANCIAL, "Payment")
def save_detail_view(request, id, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "Payment not found"}, status=500)

    payment = Payment.objects.filter(id=id, user=user, active=True).first()

    if data is None or payment is None:
        return JsonResponse({"msg": "Payment not found"}, status=404)

    if payment.status == Payment.STATUS_DONE:
        return JsonResponse({"msg": "Pagamento ja foi baixado"}, status=500)

    if data.get("payment_date"):
        payment_date = format_date(data.get("payment_date"))
        if payment_date is None:
            return JsonResponse({"msg": "Payment not found"}, status=500)

    with transaction.atomic():
        if data.get("type") is not None:
            field_type = data.get("type")
            try:
                payment.type = int(field_type)
            except (TypeError, ValueError):
                pass
        if data.get("name"):
            payment.name = data.get("name")
        if data.get("payment_date"):
            payment.payment_date = payment_date
        if data.get("fixed") is not None:
            payment.fixed = (
                boolean(data.get("fixed"))
                if not isinstance(data.get("fixed"), bool)
                else data.get("fixed")
            )
        if data.get("active") is not None:
            payment.active = (
                boolean(data.get("active"))
                if not isinstance(data.get("active"), bool)
                else data.get("active")
            )
        if data.get("value") is not None:
            old_value = payment.value
            new_value = data.get("value")
            if isinstance(new_value, str):
                new_value = float(new_value)

            invoice_value = float(payment.invoice.value_open - old_value) + new_value
            payment.invoice.value_open = invoice_value
            payment.invoice.save()

            payment.value = new_value

        try:
            payment.save()
        except Exception:
            return JsonResponse({"msg": "Payment not found"}, status=500)

    return JsonResponse({"msg": "Pagamento atualizado com sucesso"})


@require_POST
@validate_user("financial")
@audit_log("payment.payoff", CATEGORY_FINANCIAL, "Payment")
def payoff_detail_view(request, id, user):
    if id <= 0:
        return JsonResponse({"msg": "Pagamento não encontrado"}, status=404)

    payment = Payment.objects.filter(id=id, user=user, active=True).first()

    if payment is None:
        return JsonResponse({"msg": "Pagamento não encontrado"}, status=400)

    if payment.status == 1:
        return JsonResponse({"msg": "Pagamento ja baixado"}, status=400)

    with transaction.atomic():
        if payment.invoice.fixed is True:
            future_payment = payment.payment_date + timedelta(days=32)

            new_invoice = Invoice.objects.create(
                type=payment.invoice.type,
                name=payment.invoice.name,
                date=datetime.now(),
                installments=payment.invoice.installments,
                payment_date=future_payment,
                fixed=payment.invoice.fixed,
                value=payment.invoice.value,
                value_open=payment.invoice.value,
                user=user,
            )

            tags = [tag.id for tag in payment.invoice.tags.all()]
            new_invoice.tags.set(tags)
            generate_payments(new_invoice)

        payment.status = Payment.STATUS_DONE
        payment.save()

        payment.invoice.close_value(payment.value)

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

    payments_query = Payment.objects.filter(**filters, user=user).order_by(
        "payment_date", "id"
    )
    page_param = req.get("page", 1)
    page_size_param = req.get("page_size")
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

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def statement_view(request, user):
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if not date_from or not date_to:
        return JsonResponse(
            {"msg": "date_from and date_to are required"},
            status=HTTPStatus.BAD_REQUEST,
        )

    try:
        date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
        date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse(
            {"msg": "date_from and date_to must be in YYYY-MM-DD format"},
            status=HTTPStatus.BAD_REQUEST,
        )

    base_filter = Q(user=user, status=Payment.STATUS_DONE)

    # Opening balance: sum of all credits - debits with payment_date < date_from
    prior_payments = Payment.objects.filter(
        base_filter, payment_date__lt=date_from_parsed
    )
    prior_agg = prior_payments.aggregate(
        credits=Sum(
            Case(
                When(type=Payment.TYPE_CREDIT, then="value"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
        debits=Sum(
            Case(
                When(type=Payment.TYPE_DEBIT, then="value"),
                default=Value(0),
                output_field=DecimalField(),
            )
        ),
    )
    opening_balance = float((prior_agg["credits"] or 0) - (prior_agg["debits"] or 0))

    # Transactions in the period (ASC for correct running_balance, reversed later for display)
    period_payments = (
        Payment.objects.filter(
            base_filter,
            payment_date__gte=date_from_parsed,
            payment_date__lte=date_to_parsed,
        )
        .select_related("invoice")
        .prefetch_related("invoice__tags")
        .order_by("payment_date", "id")
    )

    transactions = []
    running_balance = opening_balance
    total_credits = 0.0
    total_debits = 0.0

    for payment in period_payments:
        value = float(payment.value or 0)
        if payment.type == Payment.TYPE_CREDIT:
            running_balance += value
            total_credits += value
        else:
            running_balance -= value
            total_debits += value

        invoice_name = None
        tags = []
        if payment.invoice:
            invoice_name = payment.invoice.name
            tags = [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in payment.invoice.tags.all()
            ]

        transactions.append(
            {
                "id": payment.id,
                "name": payment.name,
                "description": payment.description,
                "payment_date": (
                    payment.payment_date.isoformat() if payment.payment_date else None
                ),
                "date": payment.date.isoformat() if payment.date else None,
                "type": payment.type,
                "value": value,
                "running_balance": round(running_balance, 2),
                "invoice_name": invoice_name,
                "tags": tags,
            }
        )

    transactions.reverse()
    closing_balance = running_balance

    return JsonResponse(
        {
            "data": {
                "summary": {
                    "opening_balance": round(opening_balance, 2),
                    "total_credits": round(total_credits, 2),
                    "total_debits": round(total_debits, 2),
                    "closing_balance": round(closing_balance, 2),
                },
                "transactions": transactions,
            }
        }
    )


@require_GET
@validate_user("financial")
def statement_anomalies_view(request, user):
    serializer = StatementAnomaliesQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=HTTPStatus.BAD_REQUEST,
        )

    return JsonResponse(
        StatementAnomaliesUseCase().execute(
            user=user,
            date_from=serializer.validated_data["date_from_parsed"],
            date_to=serializer.validated_data["date_to_parsed"],
        )
    )


@require_POST
@validate_user("financial")
@audit_log("payment.csv_ai_map", CATEGORY_FINANCIAL, "Payment")
def csv_ai_map_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVAIMapInputSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": "headers is required"}, status=HTTPStatus.BAD_REQUEST
        )

    result = CSVAIMapUseCase().execute(
        headers=serializer.validated_data["headers"],
        sample_rows=serializer.validated_data.get("sample_rows"),
        import_type=serializer.validated_data.get(
            "import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
        ),
    )
    return JsonResponse(result)


@require_POST
@validate_user("financial")
@audit_log("payment.csv_ai_normalize", CATEGORY_FINANCIAL, "Payment")
def csv_ai_normalize_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVAINormalizeInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)
    transactions = serializer.get_transactions()

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    result = CSVAINormalizeUseCase().execute(transactions=transactions)
    return JsonResponse(result)


@require_POST
@validate_user("financial")
@audit_log("payment.csv_ai_reconcile", CATEGORY_FINANCIAL, "Payment")
def csv_ai_reconcile_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVAIReconcileInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)
    transactions = serializer.get_transactions()

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    matches = CSVAIReconcileUseCase().execute(
        user=user,
        transactions=transactions,
        import_type=serializer.validated_data.get(
            "import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
        ),
    )

    return JsonResponse({"matches": matches})


@require_POST
@validate_user("financial")
@audit_log("payment.ai_tag_suggestions", CATEGORY_FINANCIAL, "Payment")
def ai_tag_suggestions_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVAITagSuggestionsInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)
    transactions = serializer.get_transactions()

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    result = CSVAITagSuggestionsUseCase().execute(user=user, transactions=transactions)
    return JsonResponse(result)


@require_POST
@validate_user("financial")
@audit_log("payment.csv_mapping", CATEGORY_FINANCIAL, "Payment")
def get_csv_mapping(request, user):
    try:
        data = JSONParser().parse(request)
    except ParseError:
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVMappingInputSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse({"msg": "CSV mapping is required"}, status=400)

    csv_headers = serializer.validated_data["headers"]
    csv_mapping = GetCSVMappingUseCase().execute(csv_headers=csv_headers)

    return JsonResponse({"data": csv_mapping})


@require_POST
@validate_user("financial")
@audit_log("payment.csv_upload", CATEGORY_FINANCIAL, "Payment")
def process_csv_upload(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = ProcessCSVUploadInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)

    csv_headers: List[CSVMapping] = serializer.validated_data.get("headers", [])
    csv_body: List[Row] = serializer.validated_data.get("body", [])
    import_type: str = serializer.validated_data.get("import_type", "transactions")
    payment_date = format_date(serializer.validated_data.get("payment_date"))
    ai_suggestion_limit = serializer.validated_data.get("ai_suggestion_limit")

    processed = ProcessCSVUploadUseCase().execute(
        user=user,
        csv_headers=csv_headers,
        csv_body=csv_body,
        import_type=import_type,
        payment_date=payment_date,
        ai_suggestion_limit=ai_suggestion_limit,
    )

    return JsonResponse({"data": processed})


@require_POST
@validate_user("financial")
@audit_log("payment.csv_resolve_imports", CATEGORY_FINANCIAL, "Payment")
def csv_resolve_imports_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVResolveImportsInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)
    csv_payments: List[PaymentImport] = serializer.get_import_data()
    import_type = serializer.validated_data.get(
        "import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS
    )

    if import_type not in dict(ImportedPayment.IMPORT_SOURCES):
        return JsonResponse(
            {"msg": "Tipo de importação invalido"}, status=HTTPStatus.BAD_REQUEST
        )

    created_imported_payment = CSVResolveImportsUseCase().execute(
        user=user, csv_payments=csv_payments, import_type=import_type
    )

    return JsonResponse({"data": created_imported_payment})


@require_POST
@validate_user("financial")
@audit_log("payment.csv_import", CATEGORY_FINANCIAL, "Payment")
def csv_import_view(request, user):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = CSVImportInputSerializer(data=payload)
    serializer.is_valid(raise_exception=False)
    items = serializer.get_items()
    if items is None:
        return JsonResponse({"msg": "data is required"}, status=HTTPStatus.BAD_REQUEST)

    result = CSVImportUseCase().execute(user=user, items=items)
    if result.get("error"):
        return JsonResponse(
            result["error"]["payload"],
            status=result["error"]["status"],
        )

    return JsonResponse(result["payload"])
