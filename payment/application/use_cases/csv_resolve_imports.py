from django.db import transaction
from django.utils import timezone

from payment.models import ImportedPayment, Payment


class CSVResolveImportsUseCase:
    def _build_tag_list(self, tags_qs):
        return [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "is_budget": hasattr(tag, "budget"),
            }
            for tag in tags_qs
        ]

    def _has_budget_tag(self, tags_qs):
        return (
            tags_qs.filter(budget__isnull=False).exists()
            or tags_qs.filter(name__icontains="budget").exists()
        )

    def execute(self, user, csv_payments, import_type):
        created_imported_payment = []

        with transaction.atomic():
            for transaction_data in csv_payments:
                mapped_payment = transaction_data.get("mapped_payment")
                if not mapped_payment:
                    continue

                reference = mapped_payment.get("reference")

                matched_payment_id = transaction_data.get("matched_payment_id")
                ai_suggestion = transaction_data.get("ai_suggestion")
                ai_suggestion = ai_suggestion if isinstance(ai_suggestion, dict) else {}
                if matched_payment_id is None:
                    matched_payment_id = ai_suggestion.get("matched_payment_id")
                if matched_payment_id is not None:
                    try:
                        matched_payment_id = int(matched_payment_id)
                    except (TypeError, ValueError):
                        matched_payment_id = None

                existing = (
                    ImportedPayment.objects.filter(
                        reference=reference,
                        user=user,
                    )
                    .prefetch_related("raw_tags")
                    .first()
                )

                if existing and not existing.is_editable():
                    if existing.status == ImportedPayment.IMPORT_STATUS_COMPLETED:
                        existing_tags = existing.raw_tags.all()
                        created_imported_payment.append(
                            {
                                "import_payment_id": existing.id,
                                "reference": existing.reference,
                                "action": existing.import_strategy,
                                "payment_id": existing.matched_payment_id,
                                "name": existing.raw_name,
                                "value": float(existing.raw_value or 0),
                                "date": existing.raw_date,
                                "payment_date": existing.raw_payment_date,
                                "merge_group": existing.merge_group,
                                "tags": self._build_tag_list(existing_tags),
                                "has_budget_tag": self._has_budget_tag(existing_tags),
                                "completed": True,
                            }
                        )
                    continue

                matched_invoice_tags = []
                has_budget_tag_flag = False

                import_strategy = ImportedPayment.IMPORT_STRATEGY_NEW
                suggested_strategy = (
                    str(ai_suggestion.get("import_strategy", "")).strip().lower()
                )
                if suggested_strategy in dict(ImportedPayment.IMPORT_STRATEGIES):
                    import_strategy = suggested_strategy

                if matched_payment_id:
                    matched_payment = (
                        Payment.objects.filter(id=matched_payment_id, user=user)
                        .select_related("invoice")
                        .prefetch_related("invoice__tags")
                        .first()
                    )

                    if matched_payment:
                        import_strategy = ImportedPayment.IMPORT_STRATEGY_MERGE
                        matched_invoice_tags = matched_payment.invoice.tags.all()
                        has_budget_tag_flag = self._has_budget_tag(matched_invoice_tags)
                    else:
                        matched_payment_id = None
                        if import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE:
                            import_strategy = ImportedPayment.IMPORT_STRATEGY_NEW

                merge_group = transaction_data.get("merge_group")
                if not merge_group:
                    merge_group = ai_suggestion.get("merge_group")
                if merge_group is not None:
                    merge_group = str(merge_group).strip()[:255] or None

                imported_payment, _ = ImportedPayment.objects.update_or_create(
                    reference=reference,
                    user=user,
                    defaults={
                        "merge_group": merge_group,
                        "matched_payment_id": matched_payment_id,
                        "import_strategy": import_strategy,
                        "import_source": import_type,
                        "raw_type": mapped_payment.get("type", Payment.TYPE_DEBIT),
                        "raw_name": mapped_payment.get("name") or "",
                        "raw_description": mapped_payment.get("description") or "",
                        "raw_date": mapped_payment.get("date") or timezone.now().date(),
                        "raw_installments": mapped_payment.get("installments") or 1,
                        "raw_payment_date": mapped_payment.get("payment_date")
                        or mapped_payment.get("date")
                        or timezone.now().date(),
                        "raw_value": mapped_payment.get("value") or 0,
                        "ai_idempotency_key": str(
                            ai_suggestion.get("idempotency_key", "")
                        ).strip(),
                        "ai_suggestion_data": ai_suggestion if ai_suggestion else {},
                    },
                )

                if import_strategy == ImportedPayment.IMPORT_STRATEGY_MERGE:
                    imported_payment.raw_tags.set(matched_invoice_tags)

                created_imported_payment.append(
                    {
                        "import_payment_id": imported_payment.id,
                        "reference": imported_payment.reference,
                        "action": imported_payment.import_strategy,
                        "payment_id": matched_payment_id,
                        "name": imported_payment.raw_name,
                        "value": float(imported_payment.raw_value or 0),
                        "date": imported_payment.raw_date,
                        "payment_date": imported_payment.raw_payment_date,
                        "merge_group": imported_payment.merge_group,
                        "tags": self._build_tag_list(matched_invoice_tags),
                        "has_budget_tag": has_budget_tag_flag,
                        "ai_applied": bool(ai_suggestion),
                        "ai_suggestion": ai_suggestion if ai_suggestion else None,
                    }
                )

            merge_groups = {}
            for item in created_imported_payment:
                mg = item.get("merge_group")
                if mg:
                    merge_groups.setdefault(mg, []).append(item)

            for _, items in merge_groups.items():
                source_item = max(items, key=lambda x: len(x.get("tags", [])))
                if not source_item.get("tags"):
                    continue
                source_tag_ids = [t["id"] for t in source_item["tags"]]
                for item in items:
                    if item["import_payment_id"] == source_item["import_payment_id"]:
                        continue
                    if item.get("tags"):
                        continue
                    imp = ImportedPayment.objects.get(id=item["import_payment_id"])
                    imp.raw_tags.set(source_tag_ids)
                    item["tags"] = source_item["tags"]
                    item["has_budget_tag"] = source_item.get("has_budget_tag", False)

        return created_imported_payment
