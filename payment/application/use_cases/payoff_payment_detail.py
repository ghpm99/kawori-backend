from datetime import datetime, timedelta

from django.db import transaction

from financial.utils import generate_payments
from invoice.models import Invoice
from payment.models import Payment


class PayoffPaymentDetailUseCase:
    def execute(self, user, payment_id):
        if payment_id <= 0:
            return {
                "error": {"payload": {"msg": "Pagamento não encontrado"}, "status": 404}
            }

        payment = Payment.objects.filter(id=payment_id, user=user, active=True).first()

        if payment is None:
            return {
                "error": {"payload": {"msg": "Pagamento não encontrado"}, "status": 400}
            }

        if payment.status == 1:
            return {"error": {"payload": {"msg": "Pagamento ja baixado"}, "status": 400}}

        with transaction.atomic():
            if payment.invoice.fixed is True:
                future_payment = payment.payment_date + timedelta(days=32)

                new_invoice = Invoice.objects.create(
                    type=payment.invoice.type,
                    name=payment.invoice.name,
                    date=datetime.now(),
                    installments=payment.invoice.installments,
                    payment_date=future_payment,
                    fixed=payment.invoice.fixed,
                    value=payment.invoice.value,
                    value_open=payment.invoice.value,
                    user=user,
                )

                tags = [tag.id for tag in payment.invoice.tags.all()]
                new_invoice.tags.set(tags)
                generate_payments(new_invoice)

            payment.status = Payment.STATUS_DONE
            payment.save()

            payment.invoice.close_value(payment.value)

        return {"payload": {"msg": "Pagamento baixado"}}
