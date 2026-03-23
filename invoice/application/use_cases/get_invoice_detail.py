class GetInvoiceDetailUseCase:
    def execute(self, user, invoice_model, invoice_id):
        invoice = invoice_model.objects.filter(
            id=invoice_id, user=user, active=True
        ).first()
        if invoice is None:
            return None

        tags = [
            {
                "id": tag.id,
                "name": f"# {tag.name}" if hasattr(tag, "budget") else tag.name,
                "color": tag.color,
                "is_budget": hasattr(tag, "budget"),
            }
            for tag in invoice.tags.all().order_by("budget", "name")
        ]

        return {
            "id": invoice.id,
            "status": invoice.status,
            "name": invoice.name,
            "installments": invoice.installments,
            "value": float(invoice.value or 0),
            "value_open": float(invoice.value_open or 0),
            "value_closed": float(invoice.value_closed or 0),
            "date": invoice.date,
            "next_payment": invoice.payment_date,
            "tags": tags,
            "active": invoice.active,
        }
