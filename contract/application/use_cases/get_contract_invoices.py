class GetContractInvoicesUseCase:
    def execute(self, user, invoice_model, paginate_fn, contract_id, page, page_size):
        invoices_query = invoice_model.objects.filter(
            contract=contract_id, user=user, active=True
        ).order_by("id")

        data = paginate_fn(invoices_query, page, page_size)
        invoices = [
            {
                "id": invoice.id,
                "status": invoice.status,
                "name": invoice.name,
                "installments": invoice.installments,
                "value": float(invoice.value or 0),
                "value_open": float(invoice.value_open or 0),
                "value_closed": float(invoice.value_closed or 0),
                "date": invoice.date,
                "tags": [
                    {"id": tag.id, "name": tag.name, "color": tag.color}
                    for tag in invoice.tags.all()
                ],
            }
            for invoice in data.get("data")
        ]

        data["data"] = invoices
        return {"data": data}
