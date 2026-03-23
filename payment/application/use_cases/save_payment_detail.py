from django.db import transaction

from kawori.utils import boolean, format_date
from payment.models import Payment


class SavePaymentDetailUseCase:
    def execute(self, user, payment_id, data):
        payment = Payment.objects.filter(id=payment_id, user=user, active=True).first()

        if data is None or payment is None:
            return {"error": {"payload": {"msg": "Payment not found"}, "status": 404}}

        if payment.status == Payment.STATUS_DONE:
            return {
                "error": {"payload": {"msg": "Pagamento ja foi baixado"}, "status": 500}
            }

        if data.get("payment_date"):
            payment_date = format_date(data.get("payment_date"))
            if payment_date is None:
                return {
                    "error": {"payload": {"msg": "Payment not found"}, "status": 500}
                }

        with transaction.atomic():
            if data.get("type") is not None:
                field_type = data.get("type")
                try:
                    payment.type = int(field_type)
                except (TypeError, ValueError):
                    pass
            if data.get("name"):
                payment.name = data.get("name")
            if data.get("payment_date"):
                payment.payment_date = payment_date
            if data.get("fixed") is not None:
                payment.fixed = (
                    boolean(data.get("fixed"))
                    if not isinstance(data.get("fixed"), bool)
                    else data.get("fixed")
                )
            if data.get("active") is not None:
                payment.active = (
                    boolean(data.get("active"))
                    if not isinstance(data.get("active"), bool)
                    else data.get("active")
                )
            if data.get("value") is not None:
                old_value = payment.value
                new_value = data.get("value")
                if isinstance(new_value, str):
                    new_value = float(new_value)

                invoice_value = (
                    float(payment.invoice.value_open - old_value) + new_value
                )
                payment.invoice.value_open = invoice_value
                payment.invoice.save()

                payment.value = new_value

            try:
                payment.save()
            except Exception:
                return {
                    "error": {"payload": {"msg": "Payment not found"}, "status": 500}
                }

        return {"payload": {"msg": "Pagamento atualizado com sucesso"}}
