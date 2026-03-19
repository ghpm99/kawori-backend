from __future__ import annotations

import copy
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

from rapidfuzz import fuzz

from budget.models import Budget
from payment.models import Payment
from payment.utils import PaymentDetail, find_possible_payment_matches
from tag.models import Tag


CSV_FIELD_HINTS: dict[str, dict[str, list[tuple[str, float]]]] = {
    "payment_date": {
        "keywords": [
            ("dt pgto", 1.0),
            ("data pgto", 0.95),
            ("pagamento", 0.85),
            ("pgto", 0.85),
            ("venc", 0.75),
            ("payment date", 0.9),
            ("paid at", 0.85),
        ]
    },
    "date": {
        "keywords": [
            ("data", 0.8),
            ("date", 0.8),
            ("lancamento", 0.75),
            ("transacao", 0.75),
            ("transaction", 0.75),
            ("dt", 0.6),
        ]
    },
    "description": {
        "keywords": [
            ("hist", 0.95),
            ("descr", 0.9),
            ("memo", 0.8),
            ("narrativa", 0.75),
            ("title", 0.7),
            ("estabelecimento", 0.75),
            ("merchant", 0.75),
        ]
    },
    "name": {
        "keywords": [
            ("nome", 0.85),
            ("favorecido", 0.85),
            ("beneficiario", 0.8),
            ("payee", 0.8),
            ("title", 0.55),
            ("historico", 0.45),
        ]
    },
    "value": {
        "keywords": [
            ("valor", 1.0),
            ("vl", 0.95),
            ("amount", 0.95),
            ("total", 0.75),
            ("price", 0.7),
            ("debito", 0.65),
            ("credito", 0.65),
        ]
    },
    "installments": {
        "keywords": [
            ("parc", 1.0),
            ("parcela", 1.0),
            ("parcelado", 0.95),
            ("install", 0.95),
            ("x/", 0.6),
        ]
    },
    "reference": {
        "keywords": [
            ("id", 0.75),
            ("identificador", 1.0),
            ("refer", 0.9),
            ("protocolo", 0.8),
            ("auth", 0.75),
            ("nsu", 0.7),
            ("doc", 0.65),
        ]
    },
}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _parse_flexible_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    return None


def _parse_currency(value: Any) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    raw = str(value).strip()
    if not raw:
        return None

    is_negative = raw.startswith("(") and raw.endswith(")")
    if is_negative:
        raw = raw[1:-1]

    raw = raw.replace("R$", "").replace("r$", "")
    raw = raw.replace(" ", "")
    raw = raw.replace("\u00A0", "")

    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "")
        raw = raw.replace(",", ".")

    raw = re.sub(r"[^0-9\-.]", "", raw)

    if raw.count("-") > 1:
        return None

    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None

    if is_negative:
        amount = -amount

    return amount


def _parse_installments(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    raw = str(value).strip()
    if not raw:
        return None

    match = re.search(r"(\d+)\s*/\s*(\d+)", raw)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        if 1 <= current <= total:
            return current

    try:
        parsed = int(raw)
        return parsed if parsed > 0 else None
    except ValueError:
        return None


def _is_date_like(value: Any) -> bool:
    return _parse_flexible_date(value) is not None


def _is_money_like(value: Any) -> bool:
    parsed = _parse_currency(value)
    return parsed is not None


def _is_installments_like(value: Any) -> bool:
    return _parse_installments(value) is not None


def _is_reference_like(value: Any) -> bool:
    if value is None:
        return False

    raw = _normalize_text(str(value))
    if len(raw) < 6:
        return False

    has_digits = any(char.isdigit() for char in raw)
    has_letters = any(char.isalpha() for char in raw)

    return has_digits and has_letters


def _is_text_like(value: Any) -> bool:
    if value is None:
        return False

    raw = str(value).strip()
    if len(raw) < 3:
        return False

    return not _is_money_like(value) and not _is_date_like(value)


def _extract_sample_values(sample_rows: list[dict[str, Any]], header: str) -> list[Any]:
    values = []
    for row in sample_rows:
        if not isinstance(row, dict):
            continue
        if header not in row:
            continue

        value = row.get(header)
        if value in (None, ""):
            continue

        values.append(value)

    return values


def _pattern_score_for_field(field: str, sample_values: list[Any]) -> tuple[float, bool]:
    if not sample_values:
        return 0.0, False

    tests = {
        "payment_date": _is_date_like,
        "date": _is_date_like,
        "value": _is_money_like,
        "installments": _is_installments_like,
        "reference": _is_reference_like,
        "description": _is_text_like,
        "name": _is_text_like,
    }

    fn = tests.get(field)
    if fn is None:
        return 0.0, False

    positive_count = sum(1 for value in sample_values if fn(value))
    ratio = positive_count / max(len(sample_values), 1)

    return ratio, ratio >= 0.6


def _build_mapping_reason(field: str, has_keyword: bool, has_pattern: bool) -> str:
    pattern_reason = {
        "payment_date": "padrao de data",
        "date": "padrao de data",
        "value": "padrao monetario",
        "installments": "padrao de parcelamento",
        "reference": "padrao de referencia",
        "description": "texto descritivo",
        "name": "texto de identificacao",
    }

    reasons = []
    if has_keyword:
        reasons.append("nome da coluna")
    if has_pattern:
        reasons.append(pattern_reason.get(field, "padrao da amostra"))

    if not reasons:
        return "heuristica contextual"

    return " + ".join(reasons)


def suggest_csv_mapping(
    headers: list[str],
    sample_rows: list[dict[str, Any]] | None = None,
    import_type: str = "transactions",
) -> dict[str, Any]:
    sample_rows = sample_rows or []

    suggestions: list[dict[str, Any]] = []
    warnings: list[str] = []
    mapped_fields: dict[str, tuple[str, float]] = {}

    for header in headers:
        normalized_header = _normalize_text(header)
        sample_values = _extract_sample_values(sample_rows, header)

        ranked_fields = []
        for field, config in CSV_FIELD_HINTS.items():
            keyword_score = 0.0
            has_keyword = False

            for keyword, weight in config["keywords"]:
                if keyword in normalized_header:
                    keyword_score = max(keyword_score, weight)
                    has_keyword = True

            pattern_score, has_pattern = _pattern_score_for_field(field, sample_values)

            field_bonus = 0.0
            if field == "payment_date" and import_type == "card_payments":
                field_bonus += 0.08
            if field == "description" and "histor" in normalized_header:
                field_bonus += 0.06

            score = 0.12 + (keyword_score * 0.58) + (pattern_score * 0.36) + field_bonus
            if field in {"name", "description"} and normalized_header in {"hist", "historico", "historico"}:
                score += 0.08

            ranked_fields.append(
                {
                    "field": field,
                    "score": _clamp(score),
                    "has_keyword": has_keyword,
                    "has_pattern": has_pattern,
                }
            )

        ranked_fields.sort(key=lambda item: item["score"], reverse=True)
        best = ranked_fields[0]
        second = ranked_fields[1]

        if best["score"] < 0.35:
            warnings.append(f"Coluna '{header}' nao teve confianca suficiente para mapeamento automatico")
            continue

        system_field = best["field"]
        confidence = round(best["score"], 2)
        reason = _build_mapping_reason(system_field, best["has_keyword"], best["has_pattern"])

        previous = mapped_fields.get(system_field)
        if previous is not None:
            previous_column, previous_score = previous
            if abs(previous_score - confidence) < 0.12:
                warnings.append(
                    f"Campos '{previous_column}' e '{header}' podem representar '{system_field}'"
                )

        mapped_fields[system_field] = (header, confidence)

        if second["score"] >= 0.45 and (best["score"] - second["score"]) < 0.12:
            warnings.append(
                f"Coluna '{header}' pode ser {best['field']} ou {second['field']}"
            )

        suggestions.append(
            {
                "csv_column": header,
                "system_field": system_field,
                "confidence": confidence,
                "reason": reason,
            }
        )

    return {
        "suggestions": suggestions,
        "warnings": warnings,
    }


def normalize_csv_transactions(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_transactions: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    row_explanations: list[dict[str, Any]] = []

    for index, transaction in enumerate(transactions, start=1):
        normalized = copy.deepcopy(transaction)
        transaction_id = str(
            transaction.get("id")
            or transaction.get("transaction_id")
            or transaction.get("reference")
            or f"tx-{index}"
        )

        mapped_data_key = None
        if isinstance(normalized.get("mapped_data"), dict):
            mapped_data_key = "mapped_data"
        elif isinstance(normalized.get("mapped_payment"), dict):
            mapped_data_key = "mapped_payment"

        mapped_data = normalized.get(mapped_data_key) if mapped_data_key else None
        if not isinstance(mapped_data, dict):
            normalized_transactions.append(normalized)
            continue

        row_messages = []

        value_original = mapped_data.get("value")
        value_parsed = _parse_currency(value_original)
        if value_parsed is not None:
            value_normalized = float(value_parsed.quantize(Decimal("0.01")))
            if value_original != value_normalized:
                mapped_data["value"] = value_normalized
                message = "valor normalizado para formato decimal"
                row_messages.append(message)
                suggestions.append(
                    {
                        "transaction_id": transaction_id,
                        "row_index": index,
                        "field": "value",
                        "original_value": value_original,
                        "normalized_value": value_normalized,
                        "confidence": 0.99,
                        "reason": message,
                    }
                )

        for field in ("date", "payment_date"):
            original_value = mapped_data.get(field)
            normalized_date = _parse_flexible_date(original_value)
            if normalized_date is None:
                continue

            normalized_value = normalized_date.isoformat()
            if original_value != normalized_value:
                mapped_data[field] = normalized_value
                message = f"{field} normalizado para YYYY-MM-DD"
                row_messages.append(message)
                suggestions.append(
                    {
                        "transaction_id": transaction_id,
                        "row_index": index,
                        "field": field,
                        "original_value": original_value,
                        "normalized_value": normalized_value,
                        "confidence": 0.97,
                        "reason": message,
                    }
                )

        installments_original = mapped_data.get("installments")
        installments_parsed = _parse_installments(installments_original)
        if installments_parsed is not None and installments_original != installments_parsed:
            mapped_data["installments"] = installments_parsed
            message = "parcela convertida para inteiro"
            row_messages.append(message)
            suggestions.append(
                {
                    "transaction_id": transaction_id,
                    "row_index": index,
                    "field": "installments",
                    "original_value": installments_original,
                    "normalized_value": installments_parsed,
                    "confidence": 0.96,
                    "reason": message,
                }
            )

        for field in ("name", "description"):
            original_value = mapped_data.get(field)
            if not isinstance(original_value, str):
                continue

            normalized_value = re.sub(r"\s+", " ", original_value).strip()
            if normalized_value != original_value:
                mapped_data[field] = normalized_value
                message = f"{field} com espacamento ajustado"
                row_messages.append(message)
                suggestions.append(
                    {
                        "transaction_id": transaction_id,
                        "row_index": index,
                        "field": field,
                        "original_value": original_value,
                        "normalized_value": normalized_value,
                        "confidence": 0.9,
                        "reason": message,
                    }
                )

        if row_messages:
            row_explanations.append(
                {
                    "transaction_id": transaction_id,
                    "messages": row_messages,
                }
            )

        normalized_transactions.append(normalized)

    return {
        "normalized_transactions": normalized_transactions,
        "suggestions": suggestions,
        "total_corrections": len(suggestions),
        "row_explanations": row_explanations,
    }


def _to_payment_detail(mapped_data: dict[str, Any], user_id: int) -> PaymentDetail:
    parsed_value = _parse_currency(mapped_data.get("value")) or Decimal("0")
    parsed_date = _parse_flexible_date(mapped_data.get("date")) or date.today()
    parsed_payment_date = _parse_flexible_date(mapped_data.get("payment_date")) or parsed_date

    parsed_type = mapped_data.get("type", Payment.TYPE_DEBIT)
    try:
        parsed_type = int(parsed_type)
    except (TypeError, ValueError):
        parsed_type = Payment.TYPE_DEBIT

    parsed_installments = _parse_installments(mapped_data.get("installments")) or 1

    return PaymentDetail(
        id=None,
        status=Payment.STATUS_OPEN,
        type=parsed_type,
        name=str(mapped_data.get("name") or mapped_data.get("description") or "").strip(),
        description=str(mapped_data.get("description") or "").strip(),
        reference=str(mapped_data.get("reference") or "").strip(),
        date=parsed_date,
        installments=parsed_installments,
        payment_date=parsed_payment_date,
        fixed=False,
        active=True,
        value=parsed_value,
        invoice_id=None,
        user_id=user_id,
    )


def _build_reconcile_explanation(candidate: dict[str, Any], payment_detail: PaymentDetail) -> str:
    payment = candidate.get("payment")
    parts = []

    value_score = float(candidate.get("value_score") or 0)
    date_score = float(candidate.get("date_score") or 0)
    text_score = float(candidate.get("text_score") or 0)

    if value_score >= 0.95:
        parts.append("valor identico")
    elif value_score >= 0.8:
        parts.append("valor muito proximo")

    date_candidate = payment.payment_date if payment and payment.payment_date else payment.date if payment else None
    date_source = payment_detail.payment_date or payment_detail.date
    if date_candidate and date_source:
        day_diff = abs((date_candidate - date_source).days)
        if day_diff <= 1:
            parts.append("data proxima (1 dia)")
        elif day_diff <= 3:
            parts.append(f"data proxima ({day_diff} dias)")

    if date_score >= 0.75 and not any(part.startswith("data proxima") for part in parts):
        parts.append("compatibilidade de data")

    if text_score >= 0.8:
        parts.append("similaridade textual alta")
    elif text_score >= 0.6:
        parts.append("similaridade textual moderada")

    if not parts:
        return "match sugerido por score composto"

    return ", ".join(parts)


def suggest_reconciliation_matches(
    user,
    transactions: list[dict[str, Any]],
    import_type: str = "transactions",
) -> list[dict[str, Any]]:
    matches = []

    for index, transaction in enumerate(transactions, start=1):
        transaction_id = str(
            transaction.get("id")
            or transaction.get("transaction_id")
            or transaction.get("reference")
            or f"tx-{index}"
        )

        mapped_data = transaction.get("mapped_data")
        if not isinstance(mapped_data, dict):
            mapped_data = transaction.get("mapped_payment")

        if not isinstance(mapped_data, dict):
            matches.append(
                {
                    "transaction_id": transaction_id,
                    "best_match": None,
                    "alternatives": [],
                    "explanation": "transacao sem dados mapeados",
                }
            )
            continue

        payment_detail = _to_payment_detail(mapped_data, user.id)

        best_match = None
        alternatives = []
        explanation = "sem confianca suficiente para pre-vincular"

        if payment_detail.reference:
            exact_match = Payment.objects.filter(
                user=user,
                active=True,
                reference=payment_detail.reference,
            ).first()
            if exact_match is not None:
                best_match = {
                    "payment_id": exact_match.id,
                    "confidence": 0.99,
                }
                explanation = "referencia identica encontrada"

        candidate_matches = find_possible_payment_matches(user, payment_detail, threshold=0.4, top_n=5)

        if best_match is None and candidate_matches:
            primary = candidate_matches[0]
            primary_confidence = round(_clamp(float(primary.get("score") or 0)), 2)

            if primary_confidence >= 0.55:
                best_match = {
                    "payment_id": primary["payment"].id,
                    "confidence": primary_confidence,
                }
                explanation = _build_reconcile_explanation(primary, payment_detail)

            for candidate in candidate_matches[1:4]:
                confidence = round(_clamp(float(candidate.get("score") or 0)), 2)
                if confidence < 0.45:
                    continue
                alternatives.append(
                    {
                        "payment_id": candidate["payment"].id,
                        "confidence": confidence,
                    }
                )

        elif best_match is not None and candidate_matches:
            for candidate in candidate_matches[:3]:
                if candidate["payment"].id == best_match["payment_id"]:
                    continue
                confidence = round(_clamp(float(candidate.get("score") or 0)), 2)
                if confidence < 0.45:
                    continue
                alternatives.append(
                    {
                        "payment_id": candidate["payment"].id,
                        "confidence": confidence,
                    }
                )

        matches.append(
            {
                "transaction_id": transaction_id,
                "best_match": best_match,
                "alternatives": alternatives,
                "explanation": explanation,
            }
        )

    return matches


def _build_transaction_text(transaction: dict[str, Any]) -> str:
    mapped_data = transaction.get("mapped_data")
    if not isinstance(mapped_data, dict):
        mapped_data = transaction.get("mapped_payment")

    if not isinstance(mapped_data, dict):
        mapped_data = transaction

    text_parts = [
        str(mapped_data.get("name") or ""),
        str(mapped_data.get("description") or ""),
        str(transaction.get("original_row") or ""),
    ]

    return _normalize_text(" ".join(text_parts))


def suggest_tag_suggestions(user, transactions: list[dict[str, Any]]) -> dict[str, Any]:
    tags = list(Tag.objects.filter(user=user).order_by("name"))
    if not tags:
        return {
            "suggestions": [],
            "recommended_threshold": 0.85,
            "apply_all_count": 0,
        }

    budget_tag_ids = set(Budget.objects.filter(user=user).values_list("tag_id", flat=True))

    historical_payments = list(
        Payment.objects.filter(
            user=user,
            active=True,
            type=Payment.TYPE_DEBIT,
            invoice__tags__isnull=False,
        )
        .select_related("invoice")
        .prefetch_related("invoice__tags")
        .order_by("-payment_date")[:500]
    )

    budget_tag_frequency: Counter[int] = Counter()
    historical_text_cache: dict[int, str] = {}
    for payment in historical_payments:
        historical_text_cache[payment.id] = _normalize_text(f"{payment.name} {payment.description}")
        for tag in payment.invoice.tags.all():
            if tag.id in budget_tag_ids:
                budget_tag_frequency[tag.id] += 1

    default_budget_tag_id = None
    if budget_tag_frequency:
        default_budget_tag_id = budget_tag_frequency.most_common(1)[0][0]
    elif budget_tag_ids:
        default_budget_tag_id = next(iter(budget_tag_ids))

    response_items = []
    apply_all_count = 0

    for index, transaction in enumerate(transactions, start=1):
        transaction_id = str(
            transaction.get("id")
            or transaction.get("transaction_id")
            or transaction.get("reference")
            or f"tx-{index}"
        )

        transaction_text = _build_transaction_text(transaction)
        score_map: dict[int, float] = defaultdict(float)
        reason_map: dict[int, set[str]] = defaultdict(set)

        for tag in tags:
            tag_name = _normalize_text(tag.name)
            if not tag_name:
                continue

            direct_similarity = fuzz.token_set_ratio(transaction_text, tag_name) / 100.0
            if direct_similarity >= 0.45:
                score_map[tag.id] += direct_similarity * 0.55
                reason_map[tag.id].add("similaridade com nome da tag")

        for payment in historical_payments:
            historical_text = historical_text_cache.get(payment.id, "")
            if not historical_text:
                continue

            similarity = max(
                fuzz.token_set_ratio(transaction_text, historical_text) / 100.0,
                fuzz.partial_ratio(transaction_text, historical_text) / 100.0,
            )
            if similarity < 0.62:
                continue

            for tag in payment.invoice.tags.all():
                score_map[tag.id] += similarity
                reason_map[tag.id].add("historico de lancamentos semelhantes")

        ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)

        tag_suggestions = []
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        for tag_id, score in ranked[:3]:
            tag_obj = next((tag for tag in tags if tag.id == tag_id), None)
            if tag_obj is None:
                continue

            confidence = _clamp(0.45 + min(score, 1.8) * 0.23 + max(score - second_score, 0) * 0.25)
            reason = ", ".join(sorted(reason_map.get(tag_id) or {"perfil de gastos"}))

            tag_suggestions.append(
                {
                    "tag_id": tag_obj.id,
                    "tag_name": tag_obj.name,
                    "confidence": round(confidence, 2),
                    "reason": reason,
                    "is_budget": tag_obj.id in budget_tag_ids,
                }
            )

        needs_budget_tag = bool(budget_tag_ids) and not any(item["is_budget"] for item in tag_suggestions)
        if needs_budget_tag and default_budget_tag_id is not None:
            budget_tag = next((tag for tag in tags if tag.id == default_budget_tag_id), None)
            if budget_tag is not None:
                tag_suggestions.insert(
                    0,
                    {
                        "tag_id": budget_tag.id,
                        "tag_name": budget_tag.name,
                        "confidence": 0.72,
                        "reason": "prioridade para manter cobertura de orcamento",
                        "is_budget": True,
                    },
                )

        tag_suggestions = sorted(tag_suggestions, key=lambda item: item["confidence"], reverse=True)[:3]

        recommended_tag_id = tag_suggestions[0]["tag_id"] if tag_suggestions else None
        recommended_confidence = tag_suggestions[0]["confidence"] if tag_suggestions else 0
        if recommended_confidence >= 0.85:
            apply_all_count += 1

        response_items.append(
            {
                "transaction_id": transaction_id,
                "recommended_tag_id": recommended_tag_id,
                "tag_suggestions": tag_suggestions,
                "needs_budget_tag": needs_budget_tag,
            }
        )

    return {
        "suggestions": response_items,
        "recommended_threshold": 0.85,
        "apply_all_count": apply_all_count,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)

    if lower == upper:
        return float(ordered[lower])

    ratio = index - lower
    return float((ordered[lower] * (1 - ratio)) + (ordered[upper] * ratio))


def detect_statement_anomalies(user, begin: date, end: date) -> list[dict[str, Any]]:
    payments = list(
        Payment.objects.filter(
            user=user,
            active=True,
            status=Payment.STATUS_DONE,
            payment_date__range=(begin, end),
        )
        .select_related("invoice")
        .prefetch_related("invoice__tags")
        .order_by("-value", "-payment_date")
    )

    history_start = begin - timedelta(days=180)
    history_end = begin - timedelta(days=1)

    historical_qs = Payment.objects.filter(
        user=user,
        active=True,
        status=Payment.STATUS_DONE,
        payment_date__range=(history_start, history_end),
    )

    history_values = [float(item.value or 0) for item in historical_qs if item.value is not None]
    if not history_values:
        history_values = [float(item.value or 0) for item in payments if item.value is not None]

    baseline_median = median(history_values) if history_values else 0.0
    baseline_p90 = _percentile(history_values, 0.9)

    historical_names = {
        _normalize_text(f"{payment.name} {payment.description}")
        for payment in historical_qs
    }

    anomalies = []
    for payment in payments:
        value = float(payment.value or 0)
        if value <= 0:
            continue

        score = 0.0
        reasons = []

        if baseline_median > 0 and value >= baseline_median * 3:
            score += 0.55
            reasons.append("valor muito acima da mediana historica")
        elif baseline_p90 > 0 and value >= baseline_p90 * 1.6:
            score += 0.4
            reasons.append("valor acima do percentil 90 historico")

        payment_text = _normalize_text(f"{payment.name} {payment.description}")
        uncommon_text = payment_text and payment_text not in historical_names
        if uncommon_text and value >= max(120.0, baseline_median * 1.8):
            score += 0.25
            reasons.append("descricao pouco recorrente no historico")

        if payment.payment_date and payment.payment_date.weekday() >= 5:
            score += 0.1
            reasons.append("lancamento em fim de semana")

        if score < 0.3:
            continue

        if score >= 0.75:
            risk_level = "high"
        elif score >= 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        tags = []
        if payment.invoice_id:
            tags = [tag.name for tag in payment.invoice.tags.all()]

        anomalies.append(
            {
                "payment_id": payment.id,
                "name": payment.name,
                "description": payment.description,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "value": value,
                "type": payment.type,
                "risk_level": risk_level,
                "score": int(round(_clamp(score) * 100)),
                "explanation": ", ".join(reasons),
                "tags": tags,
            }
        )

    anomalies.sort(key=lambda item: item["score"], reverse=True)
    return anomalies
