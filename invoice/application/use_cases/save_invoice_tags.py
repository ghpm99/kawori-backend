from django.db import transaction


class SaveInvoiceTagsUseCase:
    def execute(self, user, invoice_model, tag_model, invoice_id, payload):
        if payload is None:
            return {"msg": "Etiquetas não encontradas"}, 404

        invoice = invoice_model.objects.filter(
            id=invoice_id, user=user, active=True
        ).first()
        if invoice is None:
            return {"msg": "Nota nao encontrada"}, 404

        tags = tag_model.objects.filter(id__in=payload, user=user)
        if tags.count() != len(set(payload)):
            return {"msg": "Uma ou mais tags não pertencem ao usuário"}, 400

        with transaction.atomic():
            invoice.tags.set(tags)
            invoice.save()

        return {"msg": "Etiquetas atualizadas com sucesso"}, 200
