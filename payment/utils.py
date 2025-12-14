from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
import hashlib
import json
import re
from typing import Dict, List, Optional, TypedDict

from payment.models import Payment


def csv_header_mapping(header_column):
    mapping = {
        "data": "date",
        "valor": "value",
        "amount": "amount",
        "identificador": "reference",
        "descrição": "description",
        "date": "date",
        "title": "description",
        "amount": "value",
    }
    normalized_header = header_column.strip().lower()
    return mapping.get(normalized_header, "ignore")


class CSVMapping(TypedDict):
    csv_column: str
    system_field: str


Row = Dict[str, str]


@dataclass
class PaymentDetail:
    id: Optional[int]
    status: int
    type: int
    name: str
    description: str
    reference: str
    date: date
    installments: int
    payment_date: date
    fixed: bool
    active: bool
    value: Decimal
    invoice_id: Optional[int]
    user_id: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "reference": self.reference,
            "date": self.date.isoformat() if isinstance(self.date, (date, datetime)) else self.date,
            "installments": self.installments,
            "payment_date": (
                self.payment_date.isoformat() if isinstance(self.payment_date, (date, datetime)) else self.payment_date
            ),
            "fixed": self.fixed,
            "active": self.active,
            "value": float(self.value) if isinstance(self.value, Decimal) else self.value,
            "invoice_id": self.invoice_id,
            "user_id": self.user_id,
        }


@dataclass
class ParsedTransaction:
    id: str
    original_row: Row
    mapped_data: PaymentDetail
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False
    matched_payment: Optional[PaymentDetail] = None
    match_score: Optional[float] = None
    possibly_matched_payment_list: Optional[List[PaymentDetail]] = None

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "id": self.id,
            "original_row": self.original_row,
            "validation_errors": self.validation_errors,
            "is_valid": self.is_valid,
        }
        result["mapped_data"] = self.mapped_data.to_dict() if self.mapped_data else None
        result["possibly_matched_payment_list"] = (
            [p.to_dict() for p in self.possibly_matched_payment_list] if self.possibly_matched_payment_list else None
        )
        return result


def process_csv_date(date_str: str) -> date | None:
    if not date_str or type(date_str) is not str:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def process_csv_installments(installments_str: str) -> int:
    try:
        return int(installments_str)
    except (ValueError, TypeError):
        return 1


def process_csv_value(value_str: str) -> Decimal:
    try:
        return Decimal(value_str)
    except (ValueError, TypeError):
        return Decimal(0.0)


def generate_payment_installments_by_name(name: str) -> int:
    if not name:
        return 1
    match = re.search(r"parcela\s*(\d+)\s*(?:/|de)\s*(\d+)", name, re.IGNORECASE)
    if match:
        try:
            installment = int(match.group(1))
            return installment if installment >= 1 else 1
        except ValueError:
            return 1

    # Fallback: pega qualquer ocorrência x/y isolada na string
    match = re.search(r"(\d+)\s*/\s*(\d+)", name)
    if match:
        try:
            installment = int(match.group(1))
            return installment if installment >= 1 else 1
        except ValueError:
            return 1

    return 1


def paymment_mapped_to_detail(user, import_type, mapped_data: Dict[str, any]) -> PaymentDetail:

    payment_value = mapped_data.get("value", 0.0)
    payment_type = Payment.TYPE_CREDIT
    payment_name = mapped_data.get("name", "")
    payment_description = mapped_data.get("description", "")
    payment_date = mapped_data.get("date", None)
    payment_payment_date = mapped_data.get("payment_date", None)
    payment_installments = mapped_data.get("installments", None)

    if import_type == "card_payments":
        payment_type = Payment.TYPE_DEBIT
        if payment_value < 0:
            payment_type = Payment.TYPE_CREDIT
    elif import_type == "transactions":
        if payment_value > 0:
            payment_type = Payment.TYPE_CREDIT
        else:
            payment_type = Payment.TYPE_DEBIT

    if payment_value < 0:
        payment_value = abs(payment_value)

    if not payment_name and payment_description:
        payment_name = payment_description[:255]

    if not payment_payment_date and import_type == "transactions" and payment_date:
        payment_payment_date = payment_date

    if not payment_installments:
        payment_installments = generate_payment_installments_by_name(payment_name)

    return PaymentDetail(
        id=None,
        status=0,
        type=payment_type,
        name=payment_name,
        description=payment_description,
        reference=mapped_data.get("reference", ""),
        date=payment_date or date.today(),
        installments=payment_installments or 1,
        payment_date=payment_payment_date,
        fixed=False,
        active=True,
        value=payment_value,
        invoice_id=None,
        user_id=user.id,
    )


def validate_payment_data(payment_data: PaymentDetail) -> List[str]:
    errors = []

    if not payment_data.name:
        errors.append("Nome é obrigatório.")

    if payment_data.value <= 0:
        errors.append("Valor deve ser maior que zero.")

    if payment_data.installments < 1:
        errors.append("Parcela deve ser pelo menos 1.")

    if payment_data.payment_date and payment_data.payment_date < payment_data.date:
        errors.append("Data de pagamento não pode ser antes da data da transação.")

    return errors


def generate_payment_reference(row: Row, user=None, truncate_chars: int | None = 16) -> str:

    if not isinstance(row, dict):
        payload_obj = str(row)
    else:
        sorted_keys = sorted(row.keys())
        values = [str(row.get(k, "")) for k in sorted_keys]
        payload_obj = values

    payload = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    if user is not None:
        payload = f"{user.id}|{payload}"

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if truncate_chars is not None:
        digest = digest[:truncate_chars]

    return f"ref_{digest}"


def find_possible_payment_matches(user, payment_data: PaymentDetail) -> List[PaymentDetail]:

    return []


def check_payment_is_valid(payment_data: PaymentDetail, import_type: str, validation_errors_lenght: int) -> bool:
    if import_type == "card_payments" and payment_data.name == "Pagamento recebido":
        return False
    return validation_errors_lenght == 0


def process_csv_row(user, import_type: str, header_mapping: List[CSVMapping], row: Row) -> ParsedTransaction:
    parser_transaction = ParsedTransaction(
        id=str(datetime.now().timestamp()),
        original_row=row,
        mapped_data=None,
        validation_errors=[],
        is_valid=False,
        possibly_matched_payment_list=None,
    )
    process_value = {
        "name": lambda x: x,
        "date": lambda x: process_csv_date(x),
        "installments": lambda x: process_csv_installments(x),
        "payment_date": lambda x: process_csv_date(x),
        "value": lambda x: process_csv_value(x),
        "description": lambda x: x,
        "reference": lambda x: x,
        "ignore": lambda x: None,
    }
    payment_data_mapped = {}
    for header in header_mapping:
        if header["system_field"] == "ignore":
            continue

        csv_column = header["csv_column"]
        system_field = header["system_field"]

        column_value = row.get(csv_column, "")

        process_func = process_value.get(system_field, lambda x: x)
        process_func_col = process_func(column_value)

        payment_data_mapped[system_field] = process_func_col

    payment_detail = paymment_mapped_to_detail(user, import_type, payment_data_mapped)

    if payment_detail.reference == "" or payment_detail.reference is None:
        payment_detail.reference = generate_payment_reference(row, user)

    parser_transaction.mapped_data = payment_detail
    parser_transaction.validation_errors = validate_payment_data(payment_detail)
    parser_transaction.is_valid = check_payment_is_valid(
        payment_detail, import_type, len(parser_transaction.validation_errors)
    )

    return parser_transaction
