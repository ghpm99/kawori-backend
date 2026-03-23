import json
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from financial.utils import generate_payments
from invoice.application.use_cases.get_all_invoices import GetAllInvoicesUseCase
from invoice.application.use_cases.get_invoice_detail import GetInvoiceDetailUseCase
from invoice.application.use_cases.get_invoice_payments import GetInvoicePaymentsUseCase
from invoice.application.use_cases.include_new_invoice import IncludeNewInvoiceUseCase
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
    payload, status_code = IncludeNewInvoiceUseCase().execute(
        payload=data,
        user=user,
        invoice_model=Invoice,
        tag_model=Tag,
        parse_type_fn=parse_type,
        format_date_fn=format_date,
        generate_payments_fn=generate_payments,
    )
    return JsonResponse(payload, status=status_code)


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
