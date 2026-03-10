import hashlib
import json
import operator
import re
from dataclasses import dataclass, field
from datetime import date as Date, timedelta
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import reduce
from typing import Dict, List, Optional, TypedDict

from django.db.models import Q
from django.utils import timezone
from rapidfuzz import fuzz

from invoice.models import Invoice
from payment.models import Payment


def csv_header_mapping(header_column):
    mapping = {
        "data": "date",
        "valor": "value",
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
    date: Date
    installments: int
    payment_date: Date
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
            "date": self.date.isoformat() if isinstance(self.date, (Date, datetime)) else self.date,
            "installments": self.installments,
            "payment_date": (
                self.payment_date.isoformat() if isinstance(self.payment_date, (Date, datetime)) else self.payment_date
            ),
            "fixed": self.fixed,
            "active": self.active,
            "value": float(self.value) if isinstance(self.value, Decimal) else self.value,
            "invoice_id": self.invoice_id,
            "user_id": self.user_id,
        }

    def to_invoice_model(self) -> Invoice:
        invoice = Invoice(
            id=self.id,
            status=self.status,
            type=self.type,
            name=self.name,
            date=self.date,
            installments=self.installments,
            payment_date=self.payment_date,
            fixed=self.fixed,
            active=self.active,
            value=self.value,
            user_id=self.user_id,
        )
        return invoice

    def to_payment_model(self) -> Payment:
        payment = Payment(
            id=self.id,
            status=self.status,
            type=self.type,
            name=self.name,
            description=self.description,
            reference=self.reference,
            date=self.date,
            installments=self.installments,
            payment_date=self.payment_date,
            fixed=self.fixed,
            active=self.active,
            value=self.value,
            invoice=self.to_invoice_model(),
            user_id=self.user_id,
        )
        return payment


@dataclass
class PaymentMatchCandidate:
    payment: Payment
    score: float
    days_diff: Optional[int]
    value_diff: Optional[float]
    text_score: float


@dataclass
class ParsedTransaction:
    id: str
    original_row: Row
    mapped_data: PaymentDetail
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False
    matched_payment: Optional[Payment] = None
    match_score: Optional[float] = None
    possibly_matched_payment_list: Optional[List[PaymentMatchCandidate]] = None

    def to_dict(self) -> Dict[str, object]:
        result: Dict[str, object] = {
            "id": self.id,
            "original_row": self.original_row,
            "validation_errors": self.validation_errors,
            "is_valid": self.is_valid,
        }
        result["mapped_data"] = self.mapped_data.to_dict() if self.mapped_data else None

        result["matched_payment"] = self.matched_payment.to_dict() if self.matched_payment else None

        result["possibly_matched_payment_list"] = (
            [
                {
                    "id": candidate.get("payment").id,
                    "name": candidate.get("payment").name,
                    "date": candidate.get("payment").date.isoformat(),
                    "payment_date": candidate.get("payment").payment_date.isoformat(),
                    "value": float(candidate.get("payment").value),
                    "score": int(candidate.get("score") * 100),
                }
                for candidate in self.possibly_matched_payment_list
            ]
            if self.possibly_matched_payment_list
            else None
        )
        return result


@dataclass
class PaymentImport:
    mapped_payment: PaymentDetail
    matched_payment_id: Optional[int] = None
    merge_group: Optional[str] = None


def process_csv_date(date_str: str) -> Date | None:
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
    except (ValueError, TypeError, InvalidOperation):
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


def paymment_mapped_to_detail(
    user, import_type, mapped_data: Dict[str, any], payment_date_import: datetime
) -> PaymentDetail:

    value = mapped_data.get("value", 0.0)
    type = Payment.TYPE_CREDIT
    name = mapped_data.get("name", "")
    description = mapped_data.get("description", "")
    date = mapped_data.get("date", None)
    payment_date = mapped_data.get("payment_date", None)
    installments = mapped_data.get("installments", None)

    if import_type == "card_payments":
        type = Payment.TYPE_DEBIT
        if value < 0:
            type = Payment.TYPE_CREDIT
    elif import_type == "transactions":
        if value > 0:
            type = Payment.TYPE_CREDIT
        else:
            type = Payment.TYPE_DEBIT

    if value < 0:
        value = abs(value)

    if not name and description:
        name = description[:255]

    if not payment_date and date:
        payment_date = date

    if not installments:
        installments = generate_payment_installments_by_name(name)

    return PaymentDetail(
        id=None,
        status=0,
        type=type,
        name=name,
        description=description,
        reference=mapped_data.get("reference", ""),
        date=date or Date.today(),
        installments=installments or 1,
        payment_date=payment_date_import.date() if payment_date_import else payment_date,
        fixed=False,
        active=True,
        value=value,
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


def generate_payment_reference(row: Row, user=None, truncate_chars: int | None = None) -> str:

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


def find_payment_by_reference(user, reference: str) -> Optional[Payment]:
    payment = Payment.objects.filter(
        user_id=user.id,
        reference=reference,
        active=True,
    ).first()

    return payment


def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def find_possible_payment_matches(
    user,
    payment_data: PaymentDetail,
    date_window_days: int = 45,
    top_n: int = 10,
    threshold: float = 0.45,
):

    # ---------------------------------------------------------
    # 1. FILTRO LARGO (RECALL FIRST)
    # ---------------------------------------------------------
    base_qs = Payment.objects.filter(user_id=user.id, active=True, reference="")

    delta = timedelta(days=date_window_days)
    date_clauses = []

    if payment_data.date:
        date_clauses.append(Q(date__range=(payment_data.date - delta, payment_data.date + delta)))

    if payment_data.payment_date:
        date_clauses.append(
            Q(payment_date__range=(payment_data.payment_date - delta, payment_data.payment_date + delta))
        )

    if date_clauses:
        base_qs = base_qs.filter(reduce(operator.or_, date_clauses))
    else:
        today = timezone.now().date()
        base_qs = base_qs.filter(date__range=(today - delta, today + delta))

    # ---------------------------------------------------------
    # 2. NORMALIZAÇÕES
    # ---------------------------------------------------------
    norm_name = _normalize_text(payment_data.name or "")
    norm_desc = _normalize_text(payment_data.description or "")

    pv = float(payment_data.value) if payment_data.value is not None else None

    candidates = []

    # ---------------------------------------------------------
    # 3. SCORE
    # ---------------------------------------------------------
    for p in base_qs:
        score = 0.0

        # ---------- PESOS BASE ----------
        weights = {
            "text": 0.0,  # dinâmico
            "value": 0.30,
            "date": 0.25,
            "installments": 0.10,
        }

        # ---------- DATA (usa a melhor das duas) ----------
        date_score = 0.0

        if payment_data.date and p.date:
            diff = abs((p.date - payment_data.date).days)
            date_score = max(date_score, 1.0 - (diff / date_window_days))

        if payment_data.payment_date and p.payment_date:
            diff = abs((p.payment_date - payment_data.payment_date).days)
            date_score = max(date_score, 1.0 - (diff / date_window_days))

        date_score = max(0.0, min(1.0, date_score))
        score += weights["date"] * date_score

        # ---------- VALOR ----------
        value_score = 0.0
        if pv is not None:
            try:
                pv2 = float(p.value)
                maxv = max(abs(pv), abs(pv2), 1.0)
                value_score = 1.0 - (abs(pv - pv2) / maxv)

                # PIX costuma bater valor exato
                if pv == pv2:
                    value_score = min(1.2, value_score + 0.2)

            except Exception:
                value_score = 0.0

        value_score = max(0.0, min(1.2, value_score))
        score += weights["value"] * value_score

        # ---------- TEXTO (PESO DINÂMICO) ----------
        tn = _normalize_text(p.name or "")
        td = _normalize_text(p.description or "")

        text_score_name = fuzz.token_set_ratio(norm_name, tn) / 100.0 if norm_name else 0.0
        text_score_desc = fuzz.token_set_ratio(norm_desc, td) / 100.0 if norm_desc else 0.0
        text_score = max(text_score_name, text_score_desc)

        if text_score >= 0.90:
            weights["text"] = 0.50
        elif text_score >= 0.75:
            weights["text"] = 0.35
        elif text_score >= 0.60:
            weights["text"] = 0.20
        else:
            weights["text"] = 0.05

        score += weights["text"] * text_score

        # ---------- PARCELAS (SINAL FRACO) ----------
        installment_score = 0.0
        if payment_data.installments and p.installments:
            if payment_data.installments == p.installments:
                installment_score = 1.0
            else:
                installment_score = 0.3

        score += weights["installments"] * installment_score

        # ---------- THRESHOLD ----------
        if score >= threshold:
            candidates.append(
                {
                    "payment": p,
                    "score": round(score, 4),
                    "text_score": round(text_score, 3),
                    "value_score": round(value_score, 3),
                    "date_score": round(date_score, 3),
                }
            )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]


def check_payment_is_valid(payment_data: PaymentDetail, import_type: str, validation_errors_lenght: int) -> bool:
    if import_type == "card_payments" and payment_data.name == "Pagamento recebido":
        return False
    return validation_errors_lenght == 0


def process_csv_row(
    user, import_type: str, header_mapping: List[CSVMapping], row: Row, payment_date: datetime
) -> ParsedTransaction:
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

    payment_detail = paymment_mapped_to_detail(user, import_type, payment_data_mapped, payment_date)

    if payment_detail.reference == "" or payment_detail.reference is None:
        payment_detail.reference = generate_payment_reference(row, user)

    parser_transaction.mapped_data = payment_detail
    parser_transaction.validation_errors = validate_payment_data(payment_detail)
    parser_transaction.is_valid = check_payment_is_valid(
        payment_detail, import_type, len(parser_transaction.validation_errors)
    )
    parser_transaction.matched_payment = find_payment_by_reference(user, payment_detail.reference)

    if parser_transaction.matched_payment is None:
        parser_transaction.possibly_matched_payment_list = find_possible_payment_matches(user, payment_detail)

    return parser_transaction
