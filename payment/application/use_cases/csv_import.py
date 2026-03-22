from django.db import transaction

from payment.models import ImportedPayment
from tag.models import Tag


class CSVImportUseCase:
    def execute(self, user, items):
        imported_ids = [
            item.get("import_payment_id")
            for item in items
            if item.get("import_payment_id")
        ]

        imports = ImportedPayment.objects.filter(
            id__in=imported_ids,
            user=user,
        ).select_related("matched_payment")

        imports_by_id = {imp.id: imp for imp in imports}

        count_imports = 0
        skipped = []

        with transaction.atomic():
            item_tags = {}
            merge_group_tags = {}

            for item in items:
                import_payment_id = item.get("import_payment_id")
                if not import_payment_id:
                    return {
                        "error": {
                            "payload": {"msg": "import_payment_id is required"},
                            "status": 400,
                        }
                    }

                tag_ids = item.get("tags")
                if tag_ids is None:
                    return {
                        "error": {
                            "payload": {"msg": "tags is required"},
                            "status": 400,
                        }
                    }

                item_tags[import_payment_id] = tag_ids

                imported = imports_by_id.get(import_payment_id)
                if imported and imported.merge_group and len(tag_ids) > 0:
                    merge_group_tags.setdefault(imported.merge_group, tag_ids)

            for item in items:
                import_payment_id = item.get("import_payment_id")

                imported = imports_by_id.get(import_payment_id)
                if not imported or not imported.is_editable():
                    skipped.append(
                        {
                            "import_payment_id": import_payment_id,
                            "reason": "not_editable",
                        }
                    )
                    continue

                tag_ids = item_tags.get(import_payment_id, [])

                if len(tag_ids) == 0 and imported.merge_group:
                    tag_ids = merge_group_tags.get(imported.merge_group, [])

                if len(tag_ids) == 0:
                    skipped.append(
                        {
                            "import_payment_id": import_payment_id,
                            "reason": "no_tags",
                        }
                    )
                    continue

                tags = Tag.objects.filter(
                    id__in=tag_ids,
                    user=user,
                )
                has_budget_tag = (
                    tags.filter(budget__isnull=False).exists()
                    or tags.filter(name__icontains="budget").exists()
                )
                if not has_budget_tag:
                    skipped.append(
                        {
                            "import_payment_id": import_payment_id,
                            "reason": "no_budget_tag",
                        }
                    )
                    continue

                imported.raw_tags.set(tags)
                imported.status = ImportedPayment.IMPORT_STATUS_QUEUED
                imported.save(update_fields=["status"])
                count_imports += 1

        return {
            "payload": {
                "msg": "Importação iniciada",
                "total": count_imports,
                "skipped": skipped,
            }
        }
