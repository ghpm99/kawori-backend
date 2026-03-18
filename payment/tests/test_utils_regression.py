from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from payment.models import Payment
from payment.utils import (
    ParsedTransaction,
    PaymentDetail,
    check_payment_is_valid,
    csv_header_mapping,
    find_payment_by_reference,
    find_possible_payment_matches,
    generate_payment_installments_by_name,
    generate_payment_reference,
    payment_mapped_to_detail,
    process_csv_date,
    process_csv_installments,
    process_csv_row,
    process_csv_value,
    validate_payment_data,
    _normalize_text,
)


class PaymentUtilsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="utils-user", password="123")

    def test_csv_header_mapping_variations(self):
        self.assertEqual(csv_header_mapping(" data "), "date")
        self.assertEqual(csv_header_mapping("VALOR"), "value")
        self.assertEqual(csv_header_mapping("title"), "description")
        self.assertEqual(csv_header_mapping("unknown"), "ignore")

    def test_payment_detail_converters(self):
        detail = PaymentDetail(
            id=10,
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="N",
            description="D",
            reference="R",
            date=date(2026, 1, 1),
            installments=2,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("12.34"),
            invoice_id=None,
            user_id=self.user.id,
        )
        as_dict = detail.to_dict()
        self.assertEqual(as_dict["date"], "2026-01-01")
        self.assertEqual(as_dict["payment_date"], "2026-01-02")
        self.assertEqual(as_dict["value"], 12.34)

        invoice_model = detail.to_invoice_model()
        self.assertEqual(invoice_model.name, "N")
        self.assertEqual(invoice_model.user_id, self.user.id)

        payment_model = detail.to_payment_model()
        self.assertEqual(payment_model.name, "N")
        self.assertEqual(payment_model.invoice.name, "N")

    def test_parsed_transaction_to_dict_with_candidates(self):
        matched = Payment(
            id=50,
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Matched",
            description="Desc",
            reference="ref",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 1),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            user_id=self.user.id,
        )
        detail = PaymentDetail(
            id=None,
            status=Payment.STATUS_OPEN,
            type=Payment.TYPE_DEBIT,
            name="Name",
            description="Description",
            reference="ref-x",
            date=date(2026, 1, 1),
            installments=1,
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            value=Decimal("1.00"),
            invoice_id=None,
            user_id=self.user.id,
        )
        tx = ParsedTransaction(
            id="tx-1",
            original_row={"a": "b"},
            mapped_data=detail,
            validation_errors=[],
            is_valid=True,
            matched_payment=matched,
            possibly_matched_payment_list=[
                {
                    "payment": matched,
                    "score": 0.88,
                }
            ],
        )
        data = tx.to_dict()
        self.assertEqual(data["mapped_data"]["reference"], "ref-x")
        self.assertEqual(data["matched_payment"]["name"], "Matched")
        self.assertEqual(data["possibly_matched_payment_list"][0]["score"], 88)

    def test_parse_helpers(self):
        self.assertEqual(process_csv_date("2026-01-31"), date(2026, 1, 31))
        self.assertEqual(process_csv_date("31/01/2026"), date(2026, 1, 31))
        self.assertIsNone(process_csv_date("01/31/2026"))  # MM/DD/YYYY format removed (ambiguous)
        self.assertIsNone(process_csv_date("invalid"))
        self.assertIsNone(process_csv_date(None))

        self.assertEqual(process_csv_installments("3"), 3)
        self.assertEqual(process_csv_installments("x"), 1)
        self.assertEqual(process_csv_installments(None), 1)

        self.assertEqual(process_csv_value("12.50"), Decimal("12.50"))
        self.assertEqual(process_csv_value("x"), Decimal("0"))
        self.assertEqual(process_csv_value(None), Decimal("0"))

    def test_generate_payment_installments_by_name_branches(self):
        self.assertEqual(generate_payment_installments_by_name("Parcela 2/12"), (2, 12))
        self.assertEqual(generate_payment_installments_by_name("Compra 3/10"), (3, 10))
        self.assertEqual(generate_payment_installments_by_name("Parcela 0/10"), (1, 1))
        self.assertEqual(generate_payment_installments_by_name(""), (1, 1))
        self.assertEqual(generate_payment_installments_by_name("Parcela 3/2"), (1, 1))
        self.assertEqual(generate_payment_installments_by_name("Sem parcela"), (1, 1))

    def test_payment_mapping_by_import_type(self):
        mapped = payment_mapped_to_detail(
            self.user,
            "card_payments",
            {"value": Decimal("-10"), "name": "", "description": "fallback name", "date": date(2026, 1, 1)},
            datetime(2026, 1, 15),
        )
        self.assertEqual(mapped.type, Payment.TYPE_CREDIT)
        self.assertEqual(mapped.value, Decimal("10"))
        self.assertEqual(mapped.name, "fallback name")
        self.assertEqual(mapped.installments, 1)
        self.assertEqual(mapped.payment_date, date(2026, 1, 15))

        mapped2 = payment_mapped_to_detail(
            self.user,
            "transactions",
            {"value": Decimal("-5"), "name": "Compra 4/12", "date": date(2026, 1, 2)},
            None,
        )
        self.assertEqual(mapped2.type, Payment.TYPE_DEBIT)
        self.assertEqual(mapped2.installments, 4)
        self.assertEqual(mapped2.payment_date, date(2026, 1, 2))

    def test_validate_payment_data(self):
        invalid = PaymentDetail(
            id=None,
            status=0,
            type=0,
            name="",
            description="",
            reference="",
            date=date(2026, 2, 2),
            installments=0,
            payment_date=date(2026, 2, 1),
            fixed=False,
            active=True,
            value=Decimal("0"),
            invoice_id=None,
            user_id=self.user.id,
        )
        errors = validate_payment_data(invalid)
        self.assertEqual(len(errors), 4)

        valid = PaymentDetail(
            id=None,
            status=0,
            type=0,
            name="ok",
            description="",
            reference="",
            date=date(2026, 2, 1),
            installments=1,
            payment_date=date(2026, 2, 1),
            fixed=False,
            active=True,
            value=Decimal("1"),
            invoice_id=None,
            user_id=self.user.id,
        )
        self.assertEqual(validate_payment_data(valid), [])

    def test_generate_reference_and_find_by_reference(self):
        row = {"b": "2", "a": "1"}
        ref1 = generate_payment_reference(row)
        ref2 = generate_payment_reference(row, user=self.user, truncate_chars=8)
        self.assertTrue(ref1.startswith("ref_"))
        self.assertEqual(len(ref2), 12)
        self.assertNotEqual(ref1, ref2)

        ref3 = generate_payment_reference("raw-string")
        self.assertTrue(ref3.startswith("ref_"))

        found = Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="With ref",
            description="",
            reference="abc-ref",
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            active=True,
            value=Decimal("1"),
            status=Payment.STATUS_OPEN,
            user=self.user,
        )
        self.assertEqual(find_payment_by_reference(self.user, "abc-ref").id, found.id)
        self.assertIsNone(find_payment_by_reference(self.user, "none"))

    def test_normalize_text(self):
        self.assertEqual(_normalize_text(None), "")
        self.assertEqual(_normalize_text("  Ola,\nMundo!! "), "ola mundo")

    def test_find_possible_payment_matches_db_paths(self):
        today = date.today()
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Mercado Central",
            description="Compra semanal",
            reference="",
            date=today,
            installments=3,
            payment_date=today,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
        )
        Payment.objects.create(
            type=Payment.TYPE_DEBIT,
            name="Outro Lugar",
            description="Semelhante",
            reference="",
            date=today - timedelta(days=1),
            installments=1,
            payment_date=today - timedelta(days=1),
            fixed=False,
            active=True,
            value=Decimal("50.00"),
            status=Payment.STATUS_OPEN,
            user=self.user,
        )

        payment_data = PaymentDetail(
            id=None,
            status=0,
            type=1,
            name="Mercado Central",
            description="Compra semanal",
            reference="",
            date=today,
            installments=3,
            payment_date=today,
            fixed=False,
            active=True,
            value=Decimal("100.00"),
            invoice_id=None,
            user_id=self.user.id,
        )

        candidates = find_possible_payment_matches(self.user, payment_data, threshold=0.10, top_n=1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["payment"].name, "Mercado Central")

        # cobre caminho sem datas (usa timezone.now fallback)
        payment_data_no_dates = PaymentDetail(
            **{**payment_data.__dict__, "date": None, "payment_date": None}
        )
        candidates_no_dates = find_possible_payment_matches(self.user, payment_data_no_dates, threshold=0.0)
        self.assertGreaterEqual(len(candidates_no_dates), 1)

    def test_find_possible_payment_matches_handles_value_cast_exception(self):
        class DummyQS(list):
            def filter(self, *args, **kwargs):
                return self

        dummy_payment = SimpleNamespace(
            name="Name",
            description="Desc",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            value=object(),
            id=1,
        )
        data = PaymentDetail(
            id=None,
            status=0,
            type=1,
            name="Name",
            description="Desc",
            reference="",
            date=None,
            installments=1,
            payment_date=None,
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            invoice_id=None,
            user_id=self.user.id,
        )
        with patch("payment.utils.Payment.objects.filter", return_value=DummyQS([dummy_payment])):
            candidates = find_possible_payment_matches(self.user, data, threshold=0.0)
        self.assertEqual(len(candidates), 1)

    def test_find_possible_payment_matches_text_weight_mid_ranges(self):
        class DummyQS(list):
            def filter(self, *args, **kwargs):
                return self

        dummy_payment = SimpleNamespace(
            name="Alpha",
            description="Beta",
            date=date.today(),
            payment_date=date.today(),
            installments=1,
            value=Decimal("10.00"),
            id=99,
        )
        data = PaymentDetail(
            id=None,
            status=0,
            type=1,
            name="Alpha",
            description="Beta",
            reference="",
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            active=True,
            value=Decimal("10.00"),
            invoice_id=None,
            user_id=self.user.id,
        )

        with (
            patch("payment.utils.Payment.objects.filter", return_value=DummyQS([dummy_payment])),
            patch("payment.utils.fuzz.token_set_ratio", side_effect=[80, 0]),
        ):
            candidates_80 = find_possible_payment_matches(self.user, data, threshold=0.0)
        self.assertEqual(len(candidates_80), 1)

        with (
            patch("payment.utils.Payment.objects.filter", return_value=DummyQS([dummy_payment])),
            patch("payment.utils.fuzz.token_set_ratio", side_effect=[65, 0]),
        ):
            candidates_65 = find_possible_payment_matches(self.user, data, threshold=0.0)
        self.assertEqual(len(candidates_65), 1)

    def test_check_payment_is_valid(self):
        payment_data = PaymentDetail(
            id=None,
            status=0,
            type=0,
            name="Pagamento recebido",
            description="",
            reference="",
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            active=True,
            value=Decimal("1.0"),
            invoice_id=None,
            user_id=self.user.id,
        )
        self.assertFalse(check_payment_is_valid(payment_data, "card_payments", 0))
        self.assertTrue(check_payment_is_valid(payment_data, "transactions", 0))
        self.assertFalse(check_payment_is_valid(payment_data, "transactions", 1))

    def test_process_csv_row_paths(self):
        headers = [
            {"csv_column": "descrição", "system_field": "description"},
            {"csv_column": "valor", "system_field": "value"},
            {"csv_column": "data", "system_field": "date"},
            {"csv_column": "x", "system_field": "ignore"},
        ]
        row = {"descrição": "Mercado 2/10", "valor": "15.5", "data": "2026-01-10", "x": "ignored"}

        with (
            patch("payment.utils.find_payment_by_reference", return_value=None),
            patch("payment.utils.find_possible_payment_matches", return_value=[{"payment": Mock(id=1), "score": 0.5}]),
            patch("payment.utils.generate_payment_reference", return_value="generated-ref"),
        ):
            tx = process_csv_row(self.user, "transactions", headers, row, datetime(2026, 1, 31))

        self.assertEqual(tx.mapped_data.reference, "generated-ref")
        self.assertTrue(isinstance(tx.validation_errors, list))
        self.assertIsNotNone(tx.possibly_matched_payment_list)

        existing = Payment(
            id=77,
            status=0,
            type=0,
            name="Existing",
            description="",
            reference="exists",
            date=date.today(),
            installments=1,
            payment_date=date.today(),
            fixed=False,
            active=True,
            value=Decimal("1"),
            user_id=self.user.id,
        )
        row_with_ref = {"descrição": "Pagamento recebido", "valor": "10", "data": "2026-01-10", "reference": "exists"}
        headers_with_ref = headers + [{"csv_column": "reference", "system_field": "reference"}]

        with (
            patch("payment.utils.find_payment_by_reference", return_value=existing),
            patch("payment.utils.find_possible_payment_matches") as possible_mock,
        ):
            tx2 = process_csv_row(self.user, "card_payments", headers_with_ref, row_with_ref, datetime(2026, 1, 31))

        self.assertIsNotNone(tx2.matched_payment)
        self.assertIsNone(tx2.possibly_matched_payment_list)
        possible_mock.assert_not_called()
