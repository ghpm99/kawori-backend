from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, TypedDict


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


Column = Dict[str, str]
Row = List[Column]


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


@dataclass
class ParsedTransaction:
    id: str
    original_row: Row
    mapped_data: PaymentDetail
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False
    matched_payment: Optional[PaymentDetail] = None
    match_score: Optional[float] = None
    selected: bool = False
    possibly_matched_payment_list: Optional[List[PaymentDetail]] = None


def process_csv_row(header_mapping: List[CSVMapping], row: Row) -> ParsedTransaction:
    process_value = {
        "name": lambda x: x,
        "date": lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
        "installments": lambda x: int(x),
        "payment_date": lambda x: datetime.strptime(x, "%Y-%m-%d").date(),
        "value": lambda x: float(x),
        "description": lambda x: x,
        "reference": lambda x: x,
        "ignore": lambda x: None,
    }
    processed_data = {}
    for index, header in enumerate(header_mapping):
        if header["system_field"] == "ignore":
            continue

        csv_column = header["csv_column"]
        system_field = header["system_field"]

        column_value = row.get(csv_column, "")

        process_func = process_value.get(system_field, lambda x: x)
        process_func_col = process_func(column_value)

        processed_data[system_field] = process_func_col

    return {
        original_row: row,
        mapped_data: PaymentDetail(**processed_data),
    }
