from http import HTTPStatus
import json
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


from financial.utils import generate_payments
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import boolean, format_date, paginate
from payment.models import Payment


# Create your views here.
@require_GET
@validate_user("financial")
def get_all_invoice_view(request, user):
    req = request.GET
    filters = {}

    status = req.get("status")
    if status:
        if status == "open":
            filters["value_open__gt"] = 0.0
        if status == "done":
            filters["value_open"] = 0.0
    if req.get("type"):
        filters["type"] = req.get("type")
    if req.get("fixed"):
        filters["fixed"] = boolean(req.get("fixed"))
    if req.get("name__icontains"):
        filters["name__icontains"] = req.get("name__icontains")
    if req.get("installments"):
        filters["installments"] = req.get("installments")
    if req.get("date__gte"):
        filters["date__gte"] = format_date(req.get("date__gte")) or datetime(2018, 1, 1)
    if req.get("date__lte"):
        filters["date__lte"] = format_date(req.get("date__lte")) or datetime.now() + timedelta(days=1)

    invoices_query = Invoice.objects.filter(**filters, user=user, active=True).order_by("payment_date", "id")

    page_size = req.get("page_size", 10)

    data = paginate(invoices_query, req.get("page"), page_size)

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
            "next_payment": invoice.payment_date,
            "tags": [
                {
                    "id": tag.id,
                    "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
                    "color": tag.color,
                    "is_budget": hasattr(tag, "budget"),
                }
                for tag in invoice.tags.all().order_by("budget", "name")
            ],
        }
        for invoice in data.get("data")
    ]

    data["page_size"] = page_size
    data["data"] = invoices

    return JsonResponse({"data": data})


@require_GET
@validate_user("financial")
def detail_invoice_view(request, id, user):

    invoice = Invoice.objects.filter(id=id, user=user).first()

    if invoice is None:
        return JsonResponse({"msg": "Invoice not found"}, status=404)

    tags = [
        {
            "id": tag.id,
            "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
            "color": tag.color,
            "is_budget": hasattr(tag, "budget"),
        }
        for tag in invoice.tags.all().order_by("budget", "name")
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
        "next_payment": invoice.payment_date,
        "tags": tags,
        "active": invoice.active,
    }

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
    req = request.GET
    filters = {"invoice": id}

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

    payments_query = Payment.objects.filter(**filters, user=user).order_by("id")

    page_size = req.get("page_size", 10)

    data = paginate(payments_query, req.get("page"), page_size)

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
def save_tag_invoice_view(request, id, user):

    data = json.loads(request.body)

    if data is None:
        return JsonResponse({"msg": "Etiquetas não encontradas"}, status=404)

    invoice = Invoice.objects.filter(id=id, user=user).first()
    invoice.tags.set(data)
    invoice.save()

    return JsonResponse({"msg": "Etiquetas atualizadas com sucesso"})


@require_POST
@validate_user("financial")
def include_new_invoice_view(request, user):
    data = json.loads(request.body)

    required_fields = [
        {"field": "name", "msg": "Campo nome é obrigatório"},
        {"field": "date", "msg": "Campo dia de lançamento é obrigatório"},
        {"field": "installments", "msg": "Campo parcelas é obrigatório"},
        {"field": "payment_date", "msg": "Campo dia de pagamento é obrigatório"},
        {"field": "value", "msg": "Campo valor é obrigatório"},
    ]
    for field in required_fields:
        if not data.get(field["field"]):
            return JsonResponse({"msg": field["msg"]}, status=HTTPStatus.BAD_REQUEST)

    name = data.get("name")
    date = data.get("date")
    installments = data.get("installments")
    payment_date = data.get("payment_date")
    fixed = data.get("fixed", False)
    value = data.get("value")

    invoice = Invoice.objects.create(
        status=Invoice.STATUS_OPEN,
        type=Invoice.TYPE_DEBIT,
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
        invoice.tags.set(data.get("tags"))

    generate_payments(invoice)

    return JsonResponse({"msg": "Nota inclusa com sucesso"})


@require_POST
@validate_user("financial")
def save_detail_view(request, id, user):
    data = json.loads(request.body)
    invoice = Invoice.objects.filter(id=id, user=user).first()

    if data is None or invoice is None:
        return JsonResponse({"msg": "Nota nao encontrada"}, status=404)

    if data.get("name") is not None:
        invoice.name = data.get("name")

    if data.get("date") is not None:
        invoice.date = data.get("date")

    if data.get("active") is not None:
        invoice.active = data.get("active")

    if data.get("tags") is not None:
        invoice.tags.set(data.get("tags"))

    invoice.save()

    return JsonResponse({"msg": "Nota atualizada com sucesso"})
