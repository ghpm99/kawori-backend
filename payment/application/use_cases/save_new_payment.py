from datetime import datetime
from http import HTTPStatus

from dateutil.relativedelta import relativedelta
from django.db import transaction

from financial.utils import calculate_installments
from payment.models import Payment


class SaveNewPaymentUseCase:
    def execute(self, user, data):
        installments = data.get("installments")
        payment_date = data.get("payment_date")

        value = data.get("value")
        if isinstance(value, str):
            value = float(value)

        if installments is None:
            return {
                "error": {
                    "payload": {"msg": "Erro ao incluir pagamento"},
                    "status": HTTPStatus.INTERNAL_SERVER_ERROR,
                }
            }

        if installments <= 0:
            return {"payload": {"msg": "Pagamento incluso com sucesso"}}

        value_installments = calculate_installments(value, installments)
        date_format = "%Y-%m-%d"

        try:
            with transaction.atomic():
                for i in range(installments):
                    payment = Payment(
                        type=data.get("type"),
                        name=data.get("name"),
                        date=data.get("date"),
                        installments=i + 1,
                        payment_date=payment_date,
                        fixed=data.get("fixed"),
                        value=value_installments[i],
                        user=user,
                    )
                    payment.save()
                    date_obj = datetime.strptime(payment_date, date_format)
                    future_payment = date_obj + relativedelta(months=1)
                    payment_date = future_payment.strftime(date_format)
        except Exception:
            return {
                "error": {
                    "payload": {"msg": "Erro ao incluir pagamento"},
                    "status": HTTPStatus.INTERNAL_SERVER_ERROR,
                }
            }

        return {"payload": {"msg": "Pagamento incluso com sucesso"}}
