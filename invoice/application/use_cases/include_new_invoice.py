from http import HTTPStatus

from django.db import transaction

from invoice.models import Invoice


class IncludeNewInvoiceUseCase:
    def execute(
        self,
        payload,
        user,
        invoice_model,
        tag_model,
        parse_type_fn,
        format_date_fn,
        generate_payments_fn,
    ):
        required_fields = [
            {"field": "name", "msg": "Campo nome é obrigatório"},
            {"field": "date", "msg": "Campo dia de lançamento é obrigatório"},
            {"field": "installments", "msg": "Campo parcelas é obrigatório"},
            {"field": "payment_date", "msg": "Campo dia de pagamento é obrigatório"},
            {"field": "value", "msg": "Campo valor é obrigatório"},
            {"field": "type", "msg": "Campo tipo de pagamento é obrigatório"},
        ]
        for field in required_fields:
            if not payload.get(field["field"]):
                return {"msg": field["msg"]}, HTTPStatus.BAD_REQUEST

        name = payload.get("name")
        date = payload.get("date")
        installments = payload.get("installments")
        payment_date = format_date_fn(payload.get("payment_date"))
        fixed = payload.get("fixed", False)
        value = payload.get("value")
        type_raw = payload.get("type")

        try:
            invoice_type = parse_type_fn(type_raw)
        except ValueError as e:
            return {"error": str(e)}, 400

        tags = None
        if payload.get("tags"):
            tag_ids = payload.get("tags")
            tags = tag_model.objects.filter(id__in=tag_ids, user=user)
            if tags.count() != len(set(tag_ids)):
                return {"msg": "Uma ou mais tags não pertencem ao usuário"}, 400

        with transaction.atomic():
            invoice = invoice_model.objects.create(
                status=Invoice.STATUS_OPEN,
                type=invoice_type,
                name=name,
                date=date,
                installments=installments,
                payment_date=payment_date,
                fixed=fixed,
                active=True,
                value=value,
                value_open=value,
                user=user,
            )

            if payload.get("tags"):
                invoice.tags.set(tags)

            generate_payments_fn(invoice)

        return {"msg": "Nota inclusa com sucesso"}, 200
