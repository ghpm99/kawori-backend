import hashlib
import json
from datetime import datetime, timedelta
from http import HTTPStatus
from math import ceil
from typing import List

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Case, Count, DecimalField, Q, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from financial.utils import calculate_installments, generate_payments
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.application.use_cases.get_csv_mapping import GetCSVMappingUseCase
from payment.application.use_cases.csv_ai_map import CSVAIMapUseCase
from payment.interfaces.api.serializers.csv_mapping_serializers import (
    CSVMappingInputSerializer,
)
from payment.interfaces.api.serializers.csv_ai_serializers import (
    CSVAIMapInputSerializer,
)
from payment.ai_assist import suggest_import_resolution
from payment.ai_features import (
    detect_statement_anomalies,
    normalize_csv_transactions,
    suggest_csv_mapping,
    suggest_reconciliation_matches,
    suggest_tag_suggestions,
)
from payment.models import ImportedPayment, Payment
from payment.utils import (
    CSVMapping,
    PaymentImport,
    Row,
    csv_header_mapping,
    process_csv_row,
)
from tag.models import Tag

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


def _candidate_confidence_score(parsed_row) -> float:
    candidates = getattr(parsed_row, "possibly_matched_payment_list", None) or []
    if not candidates:
        return 0.0
    top_score = float(candidates[0].get("score") or 0.0)
    second_score = (
        float(candidates[1].get("score") or 0.0) if len(candidates) > 1 else 0.0
    )
    spread = max(top_score - second_score, 0.0)
    confidence = top_score * 0.8 + spread * 0.2
    return max(0.0, min(1.0, confidence))


def _is_uncertain_confidence(score: float) -> bool:
    high = float(getattr(settings, "AI_IMPORT_HEURISTIC_HIGH_CONFIDENCE", 0.82))
    medium = float(getattr(settings, "AI_IMPORT_HEURISTIC_MEDIUM_CONFIDENCE", 0.58))
    return medium <= score < high


def _build_import_ai_idempotency_key(user_id: int, import_type: str, parsed_row) -> str:
    mapped = (
        parsed_row.mapped_data.to_dict()
        if getattr(parsed_row, "mapped_data", None)
        else {}
    )
    candidates = parsed_row.possibly_matched_payment_list or []
    payload = {
        "user_id": user_id,
        "import_type": import_type,
        "mapped_payment": {
            "reference": mapped.get("reference"),
            "name": mapped.get("name"),
            "description": mapped.get("description"),
            "date": mapped.get("date"),
            "payment_date": mapped.get("payment_date"),
            "value": mapped.get("value"),
            "installments": mapped.get("installments"),
        },
        "candidates": [
            {
                "payment_id": item["payment"].id,
                "score": item.get("score"),
                "text_score": item.get("text_score"),
                "value_score": item.get("value_score"),
                "date_score": item.get("date_score"),
            }
            for item in candidates[:5]
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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

    if date_from_parsed > date_to_parsed:
        return JsonResponse(
            {"msg": "date_from must be less than or equal to date_to"},
            status=HTTPStatus.BAD_REQUEST,
        )

    anomalies = detect_statement_anomalies(user, date_from_parsed, date_to_parsed)

    return JsonResponse(
        {
            "data": {
                "anomalies": anomalies,
                "total_anomalies": len(anomalies),
            }
        }
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

    transactions = data.get("transactions")
    if transactions is None:
        transactions = data.get("data")

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    result = normalize_csv_transactions(transactions)
    return JsonResponse(result)


@require_POST
@validate_user("financial")
@audit_log("payment.csv_ai_reconcile", CATEGORY_FINANCIAL, "Payment")
def csv_ai_reconcile_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    transactions = data.get("transactions")
    if transactions is None:
        transactions = data.get("import")

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    import_type = str(
        data.get("import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS)
    )
    matches = suggest_reconciliation_matches(
        user=user, transactions=transactions, import_type=import_type
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

    transactions = data.get("transactions")
    if transactions is None:
        transactions = data.get("data")
    if transactions is None:
        transactions = data.get("import")

    if not isinstance(transactions, list):
        return JsonResponse(
            {"msg": "transactions is required"}, status=HTTPStatus.BAD_REQUEST
        )

    result = suggest_tag_suggestions(user=user, transactions=transactions)
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

    csv_headers: List[CSVMapping] = data.get("headers", [])
    csv_body: List[Row] = data.get("body", [])
    import_type: str = data.get("import_type", "transactions")
    payment_date = format_date(data.get("payment_date"))

    processed_payments = []
    global_cap = max(int(getattr(settings, "AI_IMPORT_SUGGESTION_MAX_ITEMS", 20)), 0)
    request_cap = max(
        int(
            data.get("ai_suggestion_limit")
            or getattr(settings, "AI_IMPORT_SUGGESTION_MAX_PER_REQUEST", global_cap)
        ),
        0,
    )
    request_cap = min(request_cap, global_cap) if global_cap > 0 else request_cap

    user_daily_cap = max(
        int(getattr(settings, "AI_IMPORT_SUGGESTION_DAILY_PER_USER", 60)), 0
    )
    today = timezone.now().date()
    used_today = (
        ImportedPayment.objects.filter(
            user=user,
            updated_at__date=today,
            ai_suggestion_data__isnull=False,
        )
        .exclude(ai_suggestion_data={})
        .count()
    )
    daily_remaining = max(user_daily_cap - used_today, 0)
    max_ai_suggestions = (
        min(request_cap, daily_remaining) if user_daily_cap > 0 else request_cap
    )
    ai_attempts_left = max_ai_suggestions
    request_idempotency_cache: dict[str, dict] = {}

    for row in csv_body:
        processed_row = process_csv_row(
            user, import_type, csv_headers, row, payment_date
        )
        is_valid_row = getattr(processed_row, "is_valid", True)
        matched_payment = getattr(processed_row, "matched_payment", None)
        possible_matches = getattr(processed_row, "possibly_matched_payment_list", [])
        has_candidates = (
            is_valid_row and matched_payment is None and bool(possible_matches)
        )
        if has_candidates and ai_attempts_left > 0:
            confidence = _candidate_confidence_score(processed_row)
            if _is_uncertain_confidence(confidence):
                idempotency_key = _build_import_ai_idempotency_key(
                    user.id, import_type, processed_row
                )
                suggestion_payload = request_idempotency_cache.get(idempotency_key)

                if suggestion_payload is None:
                    existing_import = ImportedPayment.objects.filter(
                        user=user,
                        reference=processed_row.mapped_data.reference,
                        ai_idempotency_key=idempotency_key,
                    ).first()
                    if existing_import and existing_import.ai_suggestion_data:
                        suggestion_payload = dict(existing_import.ai_suggestion_data)

                if suggestion_payload is None:
                    ai_attempts_left -= 1
                    suggestion_payload = suggest_import_resolution(
                        user,
                        processed_row,
                        import_type,
                        heuristic_confidence=confidence,
                    )
                    if suggestion_payload:
                        suggestion_payload["idempotency_key"] = idempotency_key
                        request_idempotency_cache[idempotency_key] = suggestion_payload

                if suggestion_payload:
                    processed_row.ai_suggestion = suggestion_payload
        processed_payments.append(processed_row)

    processed = [pt.to_dict() for pt in processed_payments]

    return JsonResponse({"data": processed})


@require_POST
@validate_user("financial")
@audit_log("payment.csv_resolve_imports", CATEGORY_FINANCIAL, "Payment")
def csv_resolve_imports_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    csv_payments: List[PaymentImport] = data.get("import", [])
    import_type = data.get("import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS)

    created_imported_payment = []

    if import_type not in dict(ImportedPayment.IMPORT_SOURCES):
        return JsonResponse(
            {"msg": "Tipo de importação invalido"}, status=HTTPStatus.BAD_REQUEST
        )

    def _build_tag_list(tags_qs):
        return [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "is_budget": hasattr(tag, "budget"),
            }
            for tag in tags_qs
        ]

    def _has_budget_tag(tags_qs):
        return (
            tags_qs.filter(budget__isnull=False).exists()
            or tags_qs.filter(name__icontains="budget").exists()
        )

    with transaction.atomic():
        for transaction_data in csv_payments:
            mapped_payment = transaction_data.get("mapped_payment")
            if not mapped_payment:
                continue

            reference = mapped_payment.get("reference")

            matched_payment_id = transaction_data.get("matched_payment_id")
            ai_suggestion = transaction_data.get("ai_suggestion")
            ai_suggestion = ai_suggestion if isinstance(ai_suggestion, dict) else {}
            if matched_payment_id is None:
                matched_payment_id = ai_suggestion.get("matched_payment_id")
            if matched_payment_id is not None:
                try:
                    matched_payment_id = int(matched_payment_id)
                except (TypeError, ValueError):
                    matched_payment_id = None

            existing = (
                ImportedPayment.objects.filter(
                    reference=reference,
                    user=user,
                )
                .prefetch_related("raw_tags")
                .first()
            )

            if existing and not existing.is_editable():
                if existing.status == ImportedPayment.IMPORT_STATUS_COMPLETED:
                    existing_tags = existing.raw_tags.all()
                    created_imported_payment.append(
                        {
                            "import_payment_id": existing.id,
                            "reference": existing.reference,
                            "action": existing.import_strategy,
                            "payment_id": existing.matched_payment_id,
                            "name": existing.raw_name,
                            "value": float(existing.raw_value or 0),
                            "date": existing.raw_date,
                            "payment_date": existing.raw_payment_date,
                            "merge_group": existing.merge_group,
                            "tags": _build_tag_list(existing_tags),
                            "has_budget_tag": _has_budget_tag(existing_tags),
                            "completed": True,
                        }
                    )
                continue

            matched_invoice_tags = []
            has_budget_tag_flag = False

            import_strategy = ImportedPayment.IMPORT_STRATEGY_NEW
            suggested_strategy = (
                str(ai_suggestion.get("import_strategy", "")).strip().lower()
            )
            if suggested_strategy in dict(ImportedPayment.IMPORT_STRATEGIES):
                import_strategy = suggested_strategy

            if matched_payment_id:
                matched_payment = (
                    Payment.objects.filter(id=matched_payment_id, user=user)
                    .select_related("invoice")
                    .prefetch_related("invoice__tags")
                    .first()
                )

                if matched_payment:
                    import_strategy = ImportedPayment.IMPORT_STRATEGY_MERGE
                    matched_invoice_tags = matched_payment.invoice.tags.all()
                    has_budget_tag_flag = _has_budget_tag(matched_invoice_tags)
                else:
                    matched_payment_id = None
                    if import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE:
                        import_strategy = ImportedPayment.IMPORT_STRATEGY_NEW

            merge_group = transaction_data.get("merge_group")
            if not merge_group:
                merge_group = ai_suggestion.get("merge_group")
            if merge_group is not None:
                merge_group = str(merge_group).strip()[:255] or None

            imported_payment, created = ImportedPayment.objects.update_or_create(
                reference=reference,
                user=user,
                defaults={
                    "merge_group": merge_group,
                    "matched_payment_id": matched_payment_id,
                    "import_strategy": import_strategy,
                    "import_source": import_type,
                    "raw_type": mapped_payment.get("type", Payment.TYPE_DEBIT),
                    "raw_name": mapped_payment.get("name") or "",
                    "raw_description": mapped_payment.get("description") or "",
                    "raw_date": mapped_payment.get("date") or timezone.now().date(),
                    "raw_installments": mapped_payment.get("installments") or 1,
                    "raw_payment_date": mapped_payment.get("payment_date")
                    or mapped_payment.get("date")
                    or timezone.now().date(),
                    "raw_value": mapped_payment.get("value") or 0,
                    "ai_idempotency_key": str(
                        ai_suggestion.get("idempotency_key", "")
                    ).strip(),
                    "ai_suggestion_data": ai_suggestion if ai_suggestion else {},
                },
            )

            if import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE:
                imported_payment.raw_tags.set(matched_invoice_tags)

            created_imported_payment.append(
                {
                    "import_payment_id": imported_payment.id,
                    "reference": imported_payment.reference,
                    "action": imported_payment.import_strategy,
                    "payment_id": matched_payment_id,
                    "name": imported_payment.raw_name,
                    "value": float(imported_payment.raw_value or 0),
                    "date": imported_payment.raw_date,
                    "payment_date": imported_payment.raw_payment_date,
                    "merge_group": imported_payment.merge_group,
                    "tags": _build_tag_list(matched_invoice_tags),
                    "has_budget_tag": has_budget_tag_flag,
                    "ai_applied": bool(ai_suggestion),
                    "ai_suggestion": ai_suggestion if ai_suggestion else None,
                }
            )

        # Propagate tags within merge_groups
        merge_groups = {}
        for item in created_imported_payment:
            mg = item.get("merge_group")
            if mg:
                merge_groups.setdefault(mg, []).append(item)

        for mg, items in merge_groups.items():
            source_item = max(items, key=lambda x: len(x.get("tags", [])))
            if not source_item.get("tags"):
                continue
            source_tag_ids = [t["id"] for t in source_item["tags"]]
            for item in items:
                if item["import_payment_id"] == source_item["import_payment_id"]:
                    continue
                if item.get("tags"):
                    continue
                imp = ImportedPayment.objects.get(id=item["import_payment_id"])
                imp.raw_tags.set(source_tag_ids)
                item["tags"] = source_item["tags"]
                item["has_budget_tag"] = source_item.get("has_budget_tag", False)

    return JsonResponse({"data": created_imported_payment})


@require_POST
@validate_user("financial")
@audit_log("payment.csv_import", CATEGORY_FINANCIAL, "Payment")
def csv_import_view(request, user):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    items = payload.get("data")
    if items is None:
        return JsonResponse({"msg": "data is required"}, status=HTTPStatus.BAD_REQUEST)

    imported_ids = [
        item.get("import_payment_id") for item in items if item.get("import_payment_id")
    ]

    imports = ImportedPayment.objects.filter(
        id__in=imported_ids,
        user=user,
    ).select_related("matched_payment")

    imports_by_id = {imp.id: imp for imp in imports}

    count_imports = 0
    skipped = []

    with transaction.atomic():
        # First pass: collect tag assignments per item, propagating within merge_groups
        item_tags = {}
        merge_group_tags = {}

        for item in items:
            import_payment_id = item.get("import_payment_id")
            if not import_payment_id:
                return JsonResponse(
                    {"msg": "import_payment_id is required"},
                    status=HTTPStatus.BAD_REQUEST,
                )

            tag_ids = item.get("tags")
            if tag_ids is None:
                return JsonResponse(
                    {"msg": "tags is required"}, status=HTTPStatus.BAD_REQUEST
                )

            item_tags[import_payment_id] = tag_ids

            imported = imports_by_id.get(import_payment_id)
            if imported and imported.merge_group and len(tag_ids) > 0:
                merge_group_tags.setdefault(imported.merge_group, tag_ids)

        for item in items:
            import_payment_id = item.get("import_payment_id")

            imported = imports_by_id.get(import_payment_id)
            if not imported or not imported.is_editable():
                skipped.append(
                    {"import_payment_id": import_payment_id, "reason": "not_editable"}
                )
                continue

            tag_ids = item_tags.get(import_payment_id, [])

            # Propagate tags from merge_group if current item has no tags
            if len(tag_ids) == 0 and imported.merge_group:
                tag_ids = merge_group_tags.get(imported.merge_group, [])

            if len(tag_ids) == 0:
                skipped.append(
                    {"import_payment_id": import_payment_id, "reason": "no_tags"}
                )
                continue

            tags = Tag.objects.filter(
                id__in=tag_ids,
                user=user,
            )
            has_budget_tag = (
                tags.filter(budget__isnull=False).exists()
                or tags.filter(name__icontains="budget").exists()
            )
            if not has_budget_tag:
                skipped.append(
                    {"import_payment_id": import_payment_id, "reason": "no_budget_tag"}
                )
                continue

            imported.raw_tags.set(tags)
            imported.status = ImportedPayment.IMPORT_STATUS_QUEUED
            imported.save(update_fields=["status"])
            count_imports += 1

    return JsonResponse(
        {"msg": "Importação iniciada", "total": count_imports, "skipped": skipped}
    )
