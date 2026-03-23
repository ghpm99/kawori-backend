import json
from datetime import datetime, timedelta
from http import HTTPStatus

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from financial.utils import generate_payments
from invoice.application.use_cases.get_all_invoices import GetAllInvoicesUseCase
from invoice.application.use_cases.get_invoice_detail import GetInvoiceDetailUseCase
from invoice.application.use_cases.get_invoice_payments import GetInvoicePaymentsUseCase
from invoice.application.use_cases.save_invoice_detail import SaveInvoiceDetailUseCase
from invoice.application.use_cases.save_invoice_tags import SaveInvoiceTagsUseCase
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import Payment
from tag.models import Tag


def parse_type(value: str) -> int:
    try:
        return Invoice.Type[value.upper()]
    except KeyError:
        raise ValueError("Invalid type. Use 'credit' or 'debit'")


# Create your views here.
@require_GET
@validate_user("financial")
def get_all_invoice_view(request, user):
    payload = GetAllInvoicesUseCase().execute(
        request_query=request.GET,
        user=user,
        invoice_model=Invoice,
        paginate_fn=paginate,
        boolean_fn=boolean,
        format_date_fn=format_date,
    )
    return JsonResponse(payload)


@require_GET
@validate_user("financial")
def detail_invoice_view(request, id, user):
    invoice = GetInvoiceDetailUseCase().execute(
        user=user,
        invoice_model=Invoice,
        invoice_id=id,
    )
    if invoice is None:
        return JsonResponse({"msg": "Invoice not found"}, status=404)

    return JsonResponse({"data": invoice})


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
def detail_invoice_payments_view(request, id, user):
    payload = GetInvoicePaymentsUseCase().execute(
        request_query=request.GET,
        invoice_id=id,
        user=user,
        payment_model=Payment,
        paginate_fn=paginate,
        get_status_filter_fn=get_status_filter,
        format_date_fn=format_date,
        boolean_fn=boolean,
    )
    return JsonResponse(payload)


@require_POST
@validate_user("financial")
@audit_log("invoice.update_tags", CATEGORY_FINANCIAL, "Invoice")
def save_tag_invoice_view(request, id, user):
    data = json.loads(request.body)
    payload, status_code = SaveInvoiceTagsUseCase().execute(
        user=user,
        invoice_model=Invoice,
        tag_model=Tag,
        invoice_id=id,
        payload=data,
    )
    return JsonResponse(payload, status=status_code)


@require_POST
@validate_user("financial")
@audit_log("invoice.create", CATEGORY_FINANCIAL, "Invoice")
def include_new_invoice_view(request, user):
    data = json.loads(request.body)

    required_fields = [
        {"field": "name", "msg": "Campo nome é obrigatório"},
        {"field": "date", "msg": "Campo dia de lançamento é obrigatório"},
        {"field": "installments", "msg": "Campo parcelas é obrigatório"},
        {"field": "payment_date", "msg": "Campo dia de pagamento é obrigatório"},
        {"field": "value", "msg": "Campo valor é obrigatório"},
        {"field": "type", "msg": "Campo tipo de pagamento é obrigatório"},
    ]
    for field in required_fields:
        if not data.get(field["field"]):
            return JsonResponse({"msg": field["msg"]}, status=HTTPStatus.BAD_REQUEST)

    name = data.get("name")
    date = data.get("date")
    installments = data.get("installments")
    payment_date = format_date(data.get("payment_date"))
    fixed = data.get("fixed", False)
    value = data.get("value")
    type = data.get("type")

    try:
        invoice_type = parse_type(type)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if data.get("tags"):
        tag_ids = data.get("tags")
        tags = Tag.objects.filter(id__in=tag_ids, user=user)
        if tags.count() != len(set(tag_ids)):
            return JsonResponse(
                {"msg": "Uma ou mais tags não pertencem ao usuário"}, status=400
            )

    with transaction.atomic():
        invoice = Invoice.objects.create(
            status=Invoice.STATUS_OPEN,
            type=invoice_type,
            name=name,
            date=date,
            installments=installments,
            payment_date=payment_date,
            fixed=fixed,
            active=True,
            value=value,
            value_open=value,
            user=user,
        )

        if data.get("tags"):
            invoice.tags.set(tags)

        generate_payments(invoice)

    return JsonResponse({"msg": "Nota inclusa com sucesso"})


@require_POST
@validate_user("financial")
@audit_log("invoice.update", CATEGORY_FINANCIAL, "Invoice")
def save_detail_view(request, id, user):
    data = json.loads(request.body)
    payload, status_code = SaveInvoiceDetailUseCase().execute(
        user=user,
        invoice_model=Invoice,
        tag_model=Tag,
        invoice_id=id,
        payload=data,
    )
    return JsonResponse(payload, status=status_code)
