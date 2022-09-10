from datetime import datetime
from dateutil.relativedelta import relativedelta
from financial.models import Invoice, Payment


def generate_payments(invoice: Invoice):

    installments = invoice.installments
    payment_date = invoice.payment_date

    value_installments = calculate_installments(invoice.value, installments)

    date_format = '%Y-%m-%d'

    for i in range(installments):
        payment = Payment(
            type=invoice.type,
            name=invoice.name,
            date=invoice.date,
            installments=i + 1,
            payment_date=payment_date,
            fixed=invoice.fixed,
            value=value_installments[i],
            invoice=invoice
        )
        print('payment')
        print(payment)
        payment.save()
        date_obj = datetime.strptime(payment_date, date_format)
        future_payment = date_obj + relativedelta(months=1)
        payment_date = future_payment.strftime(date_format)


def calculate_installments(value, installments):

    def round(num):
        return float('%.2f' % (num))

    values = []

    if installments == 1:
        values.append(value)
        return values

    value_total = value
    index = installments
    value_installments = round(value / installments)

    for i in range(index):
        if i == index - 1:
            values.append(round(value_total))
        else:
            values.append(value_installments)
            value_total = value_total - value_installments

    return values
