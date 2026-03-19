from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from ai.assist import safe_execute_ai_task
from ai.dto import AITaskRequest, AITaskType
from payment.models import ImportedPayment


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _to_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None

    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


def _normalize_int(value: Any, *, minimum: int = 1, maximum: int = 1000) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def suggest_import_resolution(user, parsed_transaction, import_type: str) -> dict[str, Any] | None:
    mapped_data = getattr(parsed_transaction, "mapped_data", None)
    matched_payment = getattr(parsed_transaction, "matched_payment", None)
    candidates = getattr(parsed_transaction, "possibly_matched_payment_list", None) or []

    if mapped_data is None or matched_payment is not None or len(candidates) == 0:
        return None

    candidate_payload = []
    for candidate in candidates[:5]:
        payment = candidate.get("payment")
        candidate_payload.append(
            {
                "payment_id": payment.id,
                "name": payment.name,
                "description": payment.description,
                "date": payment.date.isoformat() if payment.date else None,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "installments": payment.installments,
                "value": float(payment.value) if payment.value is not None else None,
                "score": candidate.get("score"),
                "text_score": candidate.get("text_score"),
                "value_score": candidate.get("value_score"),
                "date_score": candidate.get("date_score"),
            }
        )

    payload = {
        "import_type": import_type,
        "user_id": user.id,
        "incoming_payment": mapped_data.to_dict(),
        "possible_matches": candidate_payload,
    }

    response = safe_execute_ai_task(
        AITaskRequest(
            task_type=AITaskType.STRUCTURED_EXTRACTION.value,
            input_text=_json_dumps(payload),
            instructions=(
                "Você auxilia conciliação financeira. Escolha apenas entre os candidatos fornecidos, "
                "sem inventar IDs. Se não houver confiança para merge, retorne estratégia new. "
                "Se sugerir split, mantenha matched_payment_id nulo."
            ),
            metadata={
                "schema": {
                    "import_strategy": "merge|split|new",
                    "matched_payment_id": "integer|null",
                    "merge_group": "string|null",
                    "confidence": "number_between_0_and_1",
                    "reason": "string",
                }
            },
            temperature=0.1,
            max_tokens=220,
        ),
        feature_name="payment_reconciliation",
    )
    if response is None or not isinstance(response.output, dict):
        return None

    output = response.output
    strategy = str(output.get("import_strategy", "")).strip().lower()
    if strategy not in {
        ImportedPayment.IMPORT_STRATEGY_MERGE,
        ImportedPayment.IMPORT_STRATEGY_SPLIT,
        ImportedPayment.IMPORT_STRATEGY_NEW,
    }:
        return None

    valid_candidate_ids = {item["payment_id"] for item in candidate_payload}
    suggested_payment_id = _normalize_int(output.get("matched_payment_id"), minimum=1, maximum=999999999)
    if suggested_payment_id not in valid_candidate_ids:
        suggested_payment_id = None

    merge_group = output.get("merge_group")
    merge_group = str(merge_group).strip() if merge_group is not None else None
    if merge_group == "":
        merge_group = None
    if merge_group and len(merge_group) > 255:
        merge_group = merge_group[:255]

    return {
        "import_strategy": strategy,
        "matched_payment_id": suggested_payment_id,
        "merge_group": merge_group,
        "confidence": _to_confidence(output.get("confidence")),
        "reason": str(output.get("reason", "")).strip(),
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
    }


def suggest_payment_normalization(
    main_payment: ImportedPayment,
    payments_to_process: list[ImportedPayment],
) -> dict[str, Any] | None:
    payload = {
        "main_payment": {
            "name": main_payment.raw_name,
            "description": main_payment.raw_description,
            "reference": main_payment.reference,
            "date": main_payment.raw_date.isoformat() if main_payment.raw_date else None,
            "payment_date": main_payment.raw_payment_date.isoformat() if main_payment.raw_payment_date else None,
            "value": float(main_payment.raw_value) if isinstance(main_payment.raw_value, Decimal) else main_payment.raw_value,
        },
        "merge_context": [
            {
                "name": item.raw_name,
                "description": item.raw_description,
                "value": float(item.raw_value) if isinstance(item.raw_value, Decimal) else item.raw_value,
            }
            for item in payments_to_process
        ],
    }

    response = safe_execute_ai_task(
        AITaskRequest(
            task_type=AITaskType.STRUCTURED_EXTRACTION.value,
            input_text=_json_dumps(payload),
            instructions=(
                "Normalize dados financeiros para cadastro consistente. Retorne somente JSON com nome curto, "
                "descrição consolidada, total de parcelas inferido e nomes de tags sugeridas."
            ),
            metadata={
                "schema": {
                    "normalized_name": "string",
                    "normalized_description": "string",
                    "installments_total": "integer|null",
                    "tag_names": ["string"],
                    "confidence": "number_between_0_and_1",
                    "reason": "string",
                }
            },
            temperature=0.1,
            max_tokens=260,
        ),
        feature_name="payment_normalization",
    )
    if response is None or not isinstance(response.output, dict):
        return None

    output = response.output
    normalized_name = str(output.get("normalized_name", "")).strip()
    normalized_description = str(output.get("normalized_description", "")).strip()
    if len(normalized_name) > 255:
        normalized_name = normalized_name[:255]
    if len(normalized_description) > 1024:
        normalized_description = normalized_description[:1024]

    tag_names = output.get("tag_names")
    if isinstance(tag_names, list):
        filtered_tags = []
        for tag in tag_names:
            clean_tag = str(tag).strip()
            if clean_tag and clean_tag.lower() not in {item.lower() for item in filtered_tags}:
                filtered_tags.append(clean_tag[:64])
        tag_names = filtered_tags[:8]
    else:
        tag_names = []

    return {
        "normalized_name": normalized_name,
        "normalized_description": normalized_description,
        "installments_total": _normalize_int(output.get("installments_total"), minimum=1, maximum=360),
        "tag_names": tag_names,
        "confidence": _to_confidence(output.get("confidence")),
        "reason": str(output.get("reason", "")).strip(),
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
    }
