from decimal import Decimal
from invoice.models import Invoice


class InvoiceValidationError(Exception):
    pass


def validate_invoice_data(invoice: Invoice) -> None:
    if invoice.installments < 1:
        raise InvoiceValidationError("O número de parcelas deve ser maior ou igual a 1.")

    if not invoice.user_id:
        raise InvoiceValidationError("A fatura deve estar vinculada a um usuário.")

    if not invoice.date:
        raise InvoiceValidationError("A fatura deve possuir uma data.")

    if invoice.value < Decimal("0.00"):
        raise InvoiceValidationError("O valor total da fatura não pode ser negativo.")

    if invoice.value_open < Decimal("0.00"):
        raise InvoiceValidationError("O valor em aberto da fatura não pode ser negativo.")

    if invoice.value_closed < Decimal("0.00"):
        raise InvoiceValidationError("O valor fechado da fatura não pode ser negativo.")

    if invoice.value_open > invoice.value:
        raise InvoiceValidationError("O valor em aberto não pode ser maior que o valor total da fatura.")

    if invoice.value_open + invoice.value_closed != invoice.value:
        raise InvoiceValidationError(
            "A soma do valor em aberto com o valor fechado deve ser igual ao valor total da fatura."
        )

    if invoice.status == Invoice.STATUS_DONE and invoice.value_open != Decimal("0.00"):
        raise InvoiceValidationError("Uma fatura finalizada não pode possuir valor em aberto.")

    if invoice.status == Invoice.STATUS_OPEN and invoice.value_open == Decimal("0.00"):
        raise InvoiceValidationError("Uma fatura em aberto não pode ter valor em aberto igual a zero.")
