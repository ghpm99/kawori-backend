import json
from http import HTTPStatus
from typing import List

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from audit.decorators import audit_log
from audit.models import CATEGORY_FINANCIAL
from financial.utils import generate_payments
from kawori.decorators import validate_user
from kawori.utils import format_date
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
from payment.application.use_cases.get_all_payments import GetAllPaymentsUseCase
from payment.application.use_cases.get_all_scheduled import GetAllScheduledUseCase
from payment.application.use_cases.get_csv_mapping import GetCSVMappingUseCase
from payment.application.use_cases.get_payment_detail import GetPaymentDetailUseCase
from payment.application.use_cases.get_payments_month import GetPaymentsMonthUseCase
from payment.application.use_cases.payoff_payment_detail import (
    PayoffPaymentDetailUseCase,
)
from payment.application.use_cases.process_csv_upload import ProcessCSVUploadUseCase
from payment.application.use_cases.save_new_payment import SaveNewPaymentUseCase
from payment.application.use_cases.save_payment_detail import SavePaymentDetailUseCase
from payment.application.use_cases.statement import StatementUseCase
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
from payment.interfaces.api.serializers.detail_serializers import (
    PaymentDetailPathSerializer,
    PaymentDetailResponseSerializer,
)
from payment.interfaces.api.serializers.get_all_serializers import (
    PaymentGetAllQuerySerializer,
    PaymentGetAllResponseSerializer,
)
from payment.interfaces.api.serializers.month_serializers import (
    PaymentsMonthQuerySerializer,
)
from payment.interfaces.api.serializers.payoff_detail_serializers import (
    PayoffDetailPaymentPathSerializer,
    PayoffDetailPaymentResponseSerializer,
)
from payment.interfaces.api.serializers.save_detail_serializers import (
    SaveDetailPaymentInputSerializer,
    SaveDetailPaymentPathSerializer,
    SaveDetailPaymentResponseSerializer,
)
from payment.interfaces.api.serializers.save_new_serializers import (
    SaveNewPaymentInputSerializer,
)
from payment.interfaces.api.serializers.scheduled_serializers import (
    ScheduledPaymentsQuerySerializer,
)
from payment.interfaces.api.serializers.statement_serializers import (
    StatementAnomaliesQuerySerializer,
    StatementQuerySerializer,
)
from payment.models import ImportedPayment, Payment
from payment.utils import CSVMapping, PaymentImport, Row, process_csv_row


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
    serializer = PaymentGetAllQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)
    payload = GetAllPaymentsUseCase(get_status_filter=get_status_filter).execute(
        user=user,
        params=serializer.validated_data,
    )
    response_serializer = PaymentGetAllResponseSerializer(payload)
    return JsonResponse(response_serializer.data)


@require_POST
@validate_user("financial")
@audit_log("payment.create", CATEGORY_FINANCIAL, "Payment")
def save_new_view(request, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)

    serializer = SaveNewPaymentInputSerializer(data=data)
    serializer.is_valid(raise_exception=False)

    result = SaveNewPaymentUseCase().execute(
        user=user,
        data=serializer.validated_data,
    )
    if result.get("error"):
        return JsonResponse(
            result["error"]["payload"],
            status=result["error"]["status"],
        )

    return JsonResponse(result["payload"])


@require_GET
@validate_user("financial")
def get_payments_month(request, user):
    serializer = PaymentsMonthQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]}, status=400
        )

    return JsonResponse(
        GetPaymentsMonthUseCase().execute(
            user=user,
            date_from=serializer.validated_data["date_from_parsed"],
            date_to=serializer.validated_data["date_to_parsed"],
        )
    )


@require_GET
@validate_user("financial")
def detail_view(request, id, user):
    serializer = PaymentDetailPathSerializer(data={"id": id})
    serializer.is_valid(raise_exception=False)
    data = GetPaymentDetailUseCase().execute(
        user=user,
        payment_id=serializer.validated_data["id"],
    )

    if data is None:
        return JsonResponse({"msg": "Payment not found"}, status=404)

    response_serializer = PaymentDetailResponseSerializer({"data": data})
    return JsonResponse(response_serializer.data)


@require_POST
@validate_user("financial")
@audit_log("payment.update", CATEGORY_FINANCIAL, "Payment")
def save_detail_view(request, id, user):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"msg": "Payment not found"}, status=500)

    path_serializer = SaveDetailPaymentPathSerializer(data={"id": id})
    path_serializer.is_valid(raise_exception=False)

    payload_serializer = SaveDetailPaymentInputSerializer(data=data)
    payload_serializer.is_valid(raise_exception=False)

    result = SavePaymentDetailUseCase().execute(
        user=user,
        payment_id=path_serializer.validated_data["id"],
        data=payload_serializer.validated_data,
    )
    if result.get("error"):
        return JsonResponse(
            result["error"]["payload"],
            status=result["error"]["status"],
        )

    response_serializer = SaveDetailPaymentResponseSerializer(result["payload"])
    return JsonResponse(response_serializer.data)


@require_POST
@validate_user("financial")
@audit_log("payment.payoff", CATEGORY_FINANCIAL, "Payment")
def payoff_detail_view(request, id, user):
    serializer = PayoffDetailPaymentPathSerializer(data={"id": id})
    serializer.is_valid(raise_exception=False)

    result = PayoffPaymentDetailUseCase().execute(
        user=user,
        payment_id=serializer.validated_data["id"],
        generate_payments_func=generate_payments,
    )
    if result.get("error"):
        return JsonResponse(
            result["error"]["payload"],
            status=result["error"]["status"],
        )

    response_serializer = PayoffDetailPaymentResponseSerializer(result["payload"])
    return JsonResponse(response_serializer.data)


@require_GET
@validate_user("financial")
def get_all_scheduled_view(request, user):
    serializer = ScheduledPaymentsQuerySerializer(data=request.GET)
    serializer.is_valid(raise_exception=False)
    return JsonResponse(
        GetAllScheduledUseCase(get_status_filter=get_status_filter).execute(
            user=user,
            params=serializer.validated_data,
        )
    )


@require_GET
@validate_user("financial")
def statement_view(request, user):
    serializer = StatementQuerySerializer(data=request.GET)
    if not serializer.is_valid():
        return JsonResponse(
            {"msg": serializer.errors["non_field_errors"][0]},
            status=HTTPStatus.BAD_REQUEST,
        )

    return JsonResponse(
        StatementUseCase().execute(
            user=user,
            date_from=serializer.validated_data["date_from_parsed"],
            date_to=serializer.validated_data["date_to_parsed"],
        )
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
        process_row=process_csv_row,
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
