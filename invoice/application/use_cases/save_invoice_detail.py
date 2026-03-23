from django.db import transaction


class SaveInvoiceDetailUseCase:
    def execute(self, user, invoice_model, tag_model, invoice_id, payload):
        invoice = invoice_model.objects.filter(
            id=invoice_id, user=user, active=True
        ).first()

        if payload is None or invoice is None:
            return {"msg": "Nota nao encontrada"}, 404

        tags = None
        if payload.get("tags") is not None:
            tag_ids = payload.get("tags")
            tags = tag_model.objects.filter(id__in=tag_ids, user=user)
            if tags.count() != len(set(tag_ids)):
                return {"msg": "Uma ou mais tags não pertencem ao usuário"}, 400

        with transaction.atomic():
            if payload.get("name") is not None:
                invoice.name = payload.get("name")

            if payload.get("date") is not None:
                invoice.date = payload.get("date")

            if payload.get("active") is not None:
                invoice.active = payload.get("active")

            if payload.get("tags") is not None:
                invoice.tags.set(tags)

            invoice.save()

        return {"msg": "Nota atualizada com sucesso"}, 200
