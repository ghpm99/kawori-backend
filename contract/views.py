import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from contract.application.use_cases.create_contract import CreateContractUseCase
from contract.application.use_cases.get_all_contracts import GetAllContractsUseCase
from contract.application.use_cases.get_contract_detail import GetContractDetailUseCase
from contract.application.use_cases.get_contract_invoices import (
    GetContractInvoicesUseCase,
)
from contract.application.use_cases.merge_contracts import MergeContractsUseCase
from contract.interfaces.api.serializers.contract_serializers import (
    ContractInvoicesQuerySerializer,
    ContractListQuerySerializer,
)
from contract.models import Contract
from financial.utils import generate_payments, update_contract_value
from invoice.models import Invoice
from kawori.decorators import validate_user
from kawori.utils import paginate
from tag.models import Tag


@require_GET
@validate_user("financial")
def get_all_contract_view(request, user):
    serializer = ContractListQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)

    payload = GetAllContractsUseCase().execute(
        user=user,
        contract_model=Contract,
        paginate_fn=paginate,
        contract_id=serializer.validated_data.get("id"),
        page=serializer.validated_data.get("page"),
        page_size=serializer.validated_data.get("page_size"),
    )
    return JsonResponse(payload)


@require_POST
@validate_user("financial")
@audit_log("contract.create", CATEGORY_FINANCIAL, "Contract")
def save_new_contract_view(request, user):
    data = json.loads(request.body)
    payload = CreateContractUseCase().execute(
        user=user,
        contract_model=Contract,
        payload=data,
    )
    return JsonResponse(payload)


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
    serializer = ContractInvoicesQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)

    payload = GetContractInvoicesUseCase().execute(
        user=user,
        invoice_model=Invoice,
        paginate_fn=paginate,
        contract_id=id,
        page=serializer.validated_data.get("page"),
        page_size=serializer.validated_data.get("page_size"),
    )
    return JsonResponse(payload)


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
    payload, status_code = MergeContractsUseCase().execute(
        user=user,
        contract_model=Contract,
        invoice_model=Invoice,
        contract_id=id,
        payload=data,
        update_contract_value_fn=update_contract_value,
    )
    return JsonResponse(payload, status=status_code)


@require_POST
@validate_user("financial")
@audit_log("contract.update_all_values", CATEGORY_FINANCIAL, "Contract")
def update_all_contracts_value(request, user):
    with transaction.atomic():
        contracts = Contract.objects.filter(user=user)
        for contract in contracts:
            update_contract_value(contract)
    return JsonResponse({"msg": "ok"})
