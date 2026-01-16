from dateutil.relativedelta import relativedelta

from contract.models import Contract
from invoice.models import Invoice
from payment.models import Payment


def generate_payments(invoice: Invoice, description="", reference=""):
    installments = invoice.installments
    payment_date = invoice.payment_date

    value_installments = calculate_installments(float(invoice.value), installments)

    for i in range(installments):
        payment = Payment(
            type=invoice.type,
            name=f"{invoice.name} #{i + 1}",
            description=description,
            date=invoice.date,
            installments=i + 1,
            payment_date=payment_date,
            fixed=invoice.fixed,
            value=value_installments[i],
            invoice=invoice,
            reference=reference if i == 0 else None,
            user=invoice.user,
        )
        payment.save()

        future_payment = payment_date + relativedelta(months=1)
        payment_date = future_payment


def calculate_installments(value, installments):
    def round(num):
        return float("%.2f" % (num))

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


def update_invoice_value(invoice: Invoice):
    invoice_value = 0
    invoice_value_open = 0
    invoice_value_closed = 0

    payments = Payment.objects.filter(invoice=invoice.id, active=True).all()

    for payment in payments:
        invoice_value = invoice_value + payment.value
        if payment.status == Payment.STATUS_OPEN:
            invoice_value_open = invoice_value_open + payment.value
        elif payment.status == Payment.STATUS_DONE:
            invoice_value_closed = invoice_value_closed + payment.value

    invoice.value = invoice_value
    invoice.value_open = invoice_value_open
    invoice.value_closed = invoice_value_closed

    if invoice.value_open == 0:
        invoice.status = Invoice.STATUS_DONE
    else:
        invoice.status = Invoice.STATUS_OPEN

    next_payment_date = (
        Payment.objects.filter(invoice=invoice.id, active=True, status=Payment.STATUS_OPEN)
        .order_by("payment_date")
        .first()
    )

    if next_payment_date:
        invoice.payment_date = next_payment_date.payment_date

    invoice.save()


def update_contract_value(contract: Contract):
    value = 0
    value_open = 0
    value_closed = 0

    invoices = Invoice.objects.filter(contract=contract.id, active=True).all()

    for invoice in invoices:
        update_invoice_value(invoice)

        value = value + invoice.value
        value_open = value_open + invoice.value_open
        value_closed = value_closed + invoice.value_closed

    contract.value = value
    contract.value_open = value_open
    contract.value_closed = value_closed
    contract.save()
