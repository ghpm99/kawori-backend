import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from contract.models import Contract
from financial.utils import generate_payments, update_contract_value
from invoice.models import Invoice
from kawori.decorators import add_cors_react_dev, validate_super_user
from kawori.utils import paginate


@add_cors_react_dev
@validate_super_user
@require_GET
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


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def save_new_contract_view(request, user):
    data = json.loads(request.body)
    contract = Contract(name=data.get("name"), user=user)
    contract.save()

    return JsonResponse({"msg": "Contrato incluso com sucesso"})


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_contract_view(request, id, user):
    data = Contract.objects.filter(id=id).first()

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


@add_cors_react_dev
@validate_super_user
@require_GET
def detail_contract_invoices_view(request, id, user):
    req = request.GET

    invoices_query = Invoice.objects.filter(contract=id, user=user).order_by("id")

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
            "tags": [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in invoice.tags.all()],
        }
        for invoice in data.get("data")
    ]

    data["data"] = invoices

    return JsonResponse({"data": data})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def include_new_invoice_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)

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
        invoice.tags.set(data.get("tags"))

    generate_payments(invoice)

    contract.value_open = float(contract.value_open or 0) + float(invoice.value)
    contract.value = float(contract.value or 0) + float(invoice.value)
    contract.save()

    return JsonResponse({"msg": "Nota inclusa com sucesso"})


@csrf_exempt
@add_cors_react_dev
@validate_super_user
@require_POST
def merge_contract_view(request, id, user):
    data = json.loads(request.body)

    contract = Contract.objects.filter(id=id, user=user).first()
    if contract is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)
    contracts = data.get("contracts")

    for id in contracts:
        invoices = Invoice.objects.filter(contract=id, user=user).all()
        for invoice in invoices:
            invoice.contract = contract
            invoice.save()
        Contract.objects.filter(id=id).delete()

    update_contract_value(contract)

    return JsonResponse({"msg": "Contratos mesclados com sucesso!"})
