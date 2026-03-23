from django.db import transaction


class IncludeNewInvoiceUseCase:
    def execute(
        self,
        user,
        contract_model,
        invoice_model,
        tag_model,
        contract_id,
        payload,
        generate_payments_fn,
    ):
        contract = contract_model.objects.filter(id=contract_id, user=user).first()
        if contract is None:
            return {"msg": "Contract not found"}, 404

        tags = None
        if payload.get("tags"):
            tag_ids = payload.get("tags")
            tags = tag_model.objects.filter(id__in=tag_ids, user=user)
            if tags.count() != len(set(tag_ids)):
                return {"msg": "Uma ou mais tags não pertencem ao usuário"}, 400

        with transaction.atomic():
            invoice = invoice_model(
                status=payload.get("status"),
                type=payload.get("type"),
                name=payload.get("name"),
                date=payload.get("date"),
                installments=payload.get("installments"),
                payment_date=payload.get("payment_date"),
                fixed=payload.get("fixed"),
                active=payload.get("active"),
                value=payload.get("value"),
                value_open=payload.get("value"),
                contract=contract,
                user=user,
            )
            invoice.save()
            if payload.get("tags"):
                invoice.tags.set(tags)

            generate_payments_fn(invoice)

            contract.value_open = float(contract.value_open or 0) + float(invoice.value)
            contract.value = float(contract.value or 0) + float(invoice.value)
            contract.save()

        return {"msg": "Nota inclusa com sucesso"}, 200
