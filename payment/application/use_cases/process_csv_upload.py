import hashlib
import json

from django.conf import settings
from django.utils import timezone

from payment.ai_assist import suggest_import_resolution
from payment.models import ImportedPayment
from payment.utils import process_csv_row


class ProcessCSVUploadUseCase:
    def _candidate_confidence_score(self, parsed_row) -> float:
        candidates = getattr(parsed_row, "possibly_matched_payment_list", None) or []
        if not candidates:
            return 0.0
        top_score = float(candidates[0].get("score") or 0.0)
        second_score = (
            float(candidates[1].get("score") or 0.0) if len(candidates) > 1 else 0.0
        )
        spread = max(top_score - second_score, 0.0)
        confidence = top_score * 0.8 + spread * 0.2
        return max(0.0, min(1.0, confidence))

    def _is_uncertain_confidence(self, score: float) -> bool:
        high = float(getattr(settings, "AI_IMPORT_HEURISTIC_HIGH_CONFIDENCE", 0.82))
        medium = float(
            getattr(settings, "AI_IMPORT_HEURISTIC_MEDIUM_CONFIDENCE", 0.58)
        )
        return medium <= score < high

    def _build_import_ai_idempotency_key(
        self, user_id: int, import_type: str, parsed_row
    ) -> str:
        mapped = (
            parsed_row.mapped_data.to_dict()
            if getattr(parsed_row, "mapped_data", None)
            else {}
        )
        candidates = parsed_row.possibly_matched_payment_list or []
        payload = {
            "user_id": user_id,
            "import_type": import_type,
            "mapped_payment": {
                "reference": mapped.get("reference"),
                "name": mapped.get("name"),
                "description": mapped.get("description"),
                "date": mapped.get("date"),
                "payment_date": mapped.get("payment_date"),
                "value": mapped.get("value"),
                "installments": mapped.get("installments"),
            },
            "candidates": [
                {
                    "payment_id": item["payment"].id,
                    "score": item.get("score"),
                    "text_score": item.get("text_score"),
                    "value_score": item.get("value_score"),
                    "date_score": item.get("date_score"),
                }
                for item in candidates[:5]
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def execute(
        self,
        user,
        csv_headers,
        csv_body,
        import_type,
        payment_date,
        ai_suggestion_limit,
    ):
        processed_payments = []
        global_cap = max(
            int(getattr(settings, "AI_IMPORT_SUGGESTION_MAX_ITEMS", 20)), 0
        )
        request_cap = max(
            int(
                ai_suggestion_limit
                or getattr(
                    settings,
                    "AI_IMPORT_SUGGESTION_MAX_PER_REQUEST",
                    global_cap,
                )
            ),
            0,
        )
        request_cap = min(request_cap, global_cap) if global_cap > 0 else request_cap

        user_daily_cap = max(
            int(getattr(settings, "AI_IMPORT_SUGGESTION_DAILY_PER_USER", 60)), 0
        )
        today = timezone.now().date()
        used_today = (
            ImportedPayment.objects.filter(
                user=user,
                updated_at__date=today,
                ai_suggestion_data__isnull=False,
            )
            .exclude(ai_suggestion_data={})
            .count()
        )
        daily_remaining = max(user_daily_cap - used_today, 0)
        max_ai_suggestions = (
            min(request_cap, daily_remaining) if user_daily_cap > 0 else request_cap
        )
        ai_attempts_left = max_ai_suggestions
        request_idempotency_cache = {}

        for row in csv_body:
            processed_row = process_csv_row(
                user,
                import_type,
                csv_headers,
                row,
                payment_date,
            )
            is_valid_row = getattr(processed_row, "is_valid", True)
            matched_payment = getattr(processed_row, "matched_payment", None)
            possible_matches = getattr(
                processed_row,
                "possibly_matched_payment_list",
                [],
            )
            has_candidates = (
                is_valid_row and matched_payment is None and bool(possible_matches)
            )
            if has_candidates and ai_attempts_left > 0:
                confidence = self._candidate_confidence_score(processed_row)
                if self._is_uncertain_confidence(confidence):
                    idempotency_key = self._build_import_ai_idempotency_key(
                        user.id,
                        import_type,
                        processed_row,
                    )
                    suggestion_payload = request_idempotency_cache.get(idempotency_key)

                    if suggestion_payload is None:
                        existing_import = ImportedPayment.objects.filter(
                            user=user,
                            reference=processed_row.mapped_data.reference,
                            ai_idempotency_key=idempotency_key,
                        ).first()
                        if existing_import and existing_import.ai_suggestion_data:
                            suggestion_payload = dict(existing_import.ai_suggestion_data)

                    if suggestion_payload is None:
                        ai_attempts_left -= 1
                        suggestion_payload = suggest_import_resolution(
                            user,
                            processed_row,
                            import_type,
                            heuristic_confidence=confidence,
                        )
                        if suggestion_payload:
                            suggestion_payload["idempotency_key"] = idempotency_key
                            request_idempotency_cache[idempotency_key] = (
                                suggestion_payload
                            )

                    if suggestion_payload:
                        processed_row.ai_suggestion = suggestion_payload
            processed_payments.append(processed_row)

        return [pt.to_dict() for pt in processed_payments]
