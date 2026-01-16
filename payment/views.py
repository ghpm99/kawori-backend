from http import HTTPStatus
import json
from datetime import datetime, timedelta
from typing import List

from dateutil.relativedelta import relativedelta
from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from financial.utils import calculate_installments, generate_payments
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import ImportedPayment, Payment
from payment.utils import (
    CSVMapping,
    PaymentImport,
    Row,
    csv_header_mapping,
    process_csv_row,
)
from tag.models import Tag


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
    if req.get("invoice_id"):
        filters["invoice_id"] = req.get("invoice_id")
    if req.get("invoice"):
        filters["invoice__name__icontains"] = req.get("invoice")

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
                AND fi.active = true
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

    if payment.invoice.fixed is True:
        future_payment = payment.payment_date + relativedelta(months=1)

        with transaction.atomic():
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
def get_csv_mapping(request, user):
    data = json.loads(request.body)

    csv_headers = data.get("headers")

    if not csv_headers:
        return JsonResponse({"msg": "CSV mapping is required"}, status=400)

    csv_mapping = [{"csv_column": col, "system_field": csv_header_mapping(col)} for col in csv_headers]

    return JsonResponse({"data": csv_mapping})


@require_POST
@validate_user("financial")
def process_csv_upload(request, user):
    data = json.loads(request.body)

    csv_headers: List[CSVMapping] = data.get("headers", [])
    csv_body: List[Row] = data.get("body", [])
    import_type: str = data.get("import_type", "transactions")
    payment_date = format_date(data.get("payment_date"))

    processed_payments = []

    for row in csv_body:
        processed_row = process_csv_row(user, import_type, csv_headers, row, payment_date)
        processed_payments.append(processed_row)

    processed = [pt.to_dict() for pt in processed_payments]

    return JsonResponse({"data": processed})


@require_POST
@validate_user("financial")
def csv_resolve_imports_view(request, user):
    data = json.loads(request.body)

    csv_payments: List[PaymentImport] = data.get("import", [])
    import_type = data.get("import_type", ImportedPayment.IMPORT_SOURCE_TRANSACTIONS)

    created_imported_payment = []

    if import_type not in dict(ImportedPayment.IMPORT_SOURCES):
        return JsonResponse({"msg": "Tipo de importação invalido"}, status=HTTPStatus.BAD_REQUEST)

    for transaction_data in csv_payments:
        mapped_payment = transaction_data.get("mapped_payment")
        if not mapped_payment:
            continue

        reference = mapped_payment.get("reference")

        matched_payment_id = transaction_data.get("matched_payment_id")

        existing = ImportedPayment.objects.filter(
            reference=reference,
            user=user,
        ).first()

        if existing and not existing.is_editable():
            continue

        matched_invoice_tags = []
        has_budget_tag = False

        import_strategy = ImportedPayment.IMPORT_STRATEGY_NEW

        if matched_payment_id:
            import_strategy = ImportedPayment.IMPORT_STRATEGY_MERGE

            matched_payment = (
                Payment.objects.filter(id=matched_payment_id, user=user)
                .select_related("invoice")
                .prefetch_related("invoice__tags")
                .first()
            )

            if not matched_payment:
                continue

            matched_invoice_tags = matched_payment.invoice.tags.all()
            has_budget_tag = matched_payment.invoice.tags.filter(budget__isnull=False).exists()

        imported_payment, created = ImportedPayment.objects.update_or_create(
            reference=reference,
            user=user,
            defaults={
                "merge_group": transaction_data.get("merge_group"),
                "matched_payment_id": matched_payment_id,
                "import_strategy": import_strategy,
                "import_source": import_type,
                "raw_type": mapped_payment.get("type"),
                "raw_name": mapped_payment.get("name"),
                "raw_description": mapped_payment.get("description"),
                "raw_date": mapped_payment.get("date"),
                "raw_installments": mapped_payment.get("installments"),
                "raw_payment_date": mapped_payment.get("payment_date"),
                "raw_value": mapped_payment.get("value"),
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
                "tags": [
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "color": tag.color,
                        "is_budget": hasattr(tag, "budget"),
                    }
                    for tag in matched_invoice_tags
                ],
                "has_budget_tag": has_budget_tag,
            }
        )

    return JsonResponse({"data": created_imported_payment})


@require_POST
@validate_user("financial")
def csv_import_view(request, user):
    payload = json.loads(request.body)

    items = payload.get("data", [])

    imported_ids = [item["import_payment_id"] for item in items]

    imports = ImportedPayment.objects.filter(
        id__in=imported_ids,
        user=user,
    ).select_related("matched_payment")

    imports_by_id = {imp.id: imp for imp in imports}

    count_imports = 0

    for item in items:
        imported = imports_by_id.get(item["import_payment_id"])
        if not imported or not imported.is_editable():
            continue

        tags = Tag.objects.filter(
            id__in=item["tags"],
            user=user,
        )
        has_budget_tag = tags.filter(budget__isnull=False).exists()
        if not has_budget_tag:
            continue

        imported.raw_tags.set(tags)
        imported.status = ImportedPayment.IMPORT_STATUS_QUEUED
        imported.save(update_fields=["status"])
        count_imports += 1

    return JsonResponse({"msg": "Importação iniciada", "total": count_imports})
