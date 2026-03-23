import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from contract.application.use_cases.get_contract_detail import GetContractDetailUseCase
from contract.models import Contract
from financial.utils import generate_payments, update_contract_value
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import paginate
from tag.models import Tag


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


@require_POST
@validate_user("financial")
@audit_log("contract.create", CATEGORY_FINANCIAL, "Contract")
def save_new_contract_view(request, user):
    data = json.loads(request.body)
    contract = Contract(name=data.get("name"), user=user)
    contract.save()

    return JsonResponse(
        {
            "data": {
                "id": contract.id,
                "name": contract.name,
                "value": float(contract.value or 0),
                "value_open": float(contract.value_open or 0),
                "value_closed": float(contract.value_closed or 0),
            }
        }
    )


@require_GET
@validate_user("financial")
def detail_contract_view(request, id, user):
    contract = GetContractDetailUseCase().execute(
        user=user,
        contract_model=Contract,
        contract_id=id,
    )
    if contract is None:
        return JsonResponse({"msg": "Contract not found"}, status=404)

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
@audit_log("contract.invoice.create", CATEGORY_FINANCIAL, "Invoice")
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


@require_POST
@validate_user("financial")
@audit_log("contract.merge", CATEGORY_FINANCIAL, "Contract")
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


@require_POST
@validate_user("financial")
@audit_log("contract.update_all_values", CATEGORY_FINANCIAL, "Contract")
def update_all_contracts_value(request, user):
    with transaction.atomic():
        contracts = Contract.objects.filter(user=user)
        for contract in contracts:
            update_contract_value(contract)
    return JsonResponse({"msg": "ok"})
