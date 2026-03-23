from payment.models import Payment


class GetPaymentDetailUseCase:
    def execute(self, user, payment_id):
        data = Payment.objects.filter(id=payment_id, user=user, active=True).first()
        if data is None:
            return None

        return {
            "id": data.id,
            "status": data.status,
            "type": data.type,
            "name": data.name,
            "date": data.date,
            "installments": data.installments,
            "payment_date": data.payment_date,
            "fixed": data.fixed,
            "active": data.active,
            "value": float(data.value or 0),
            "invoice": data.invoice.id,
            "invoice_name": data.invoice.name,
        }
