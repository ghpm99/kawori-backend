import json

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
from contract.application.use_cases.include_new_invoice import IncludeNewInvoiceUseCase
from contract.application.use_cases.merge_contracts import MergeContractsUseCase
from contract.application.use_cases.update_all_contracts_value import (
    UpdateAllContractsValueUseCase,
)
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
    payload, status_code = IncludeNewInvoiceUseCase().execute(
        user=user,
        contract_model=Contract,
        invoice_model=Invoice,
        tag_model=Tag,
        contract_id=id,
        payload=data,
        generate_payments_fn=generate_payments,
    )
    return JsonResponse(payload, status=status_code)


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
    payload, status_code = UpdateAllContractsValueUseCase().execute(
        user=user,
        contract_model=Contract,
        update_contract_value_fn=update_contract_value,
    )
    return JsonResponse(payload, status=status_code)
