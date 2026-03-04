from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from budget.models import Budget
from contract.models import Contract
from invoice.models import Invoice
from payment.models import Payment
from tag.models import Tag

from financial.management.commands import ONEOFF_20220910_GENERATE_INVOICE as cmd_generate_invoice
from financial.management.commands import ONEOFF_20231003_UPDATE_FINANCIAL_HOME_PAYMENT_DATE as cmd_update_home_date
from financial.management.commands import ONEOFF_20231006_UPDATE_FINANCING_VALUE as cmd_update_financing
from financial.management.commands import ONEOFF_20250111_MIGRATE_MODEL as cmd_migrate_model
from financial.management.commands import ONEOFF_20251106_CONTRACT_TO_TAG as cmd_contract_to_tag
from financial.management.commands import ONEOFF_20260104_FIX_PAYMENT_REFERENCE as cmd_fix_reference
from financial.management.commands import ONEOFF_20260104_UPDATE_PAYMENT_DATE as cmd_update_payment_date
from financial.management.commands import cron_payment_discord as cmd_discord
from financial.management.commands import cron_payment_email as cmd_email
from financial.management.commands import cron_recalculate_invoices as cmd_recalculate
from financial.management.commands import process_imported_payments as cmd_process_imported


class FinancialManagementCommandsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="cmd-reg", email="cmd-reg@test.com", password="123")

    def _create_invoice(self, **kwargs):
        return Invoice.objects.create(
            status=kwargs.get("status", Invoice.STATUS_OPEN),
            type=kwargs.get("type", Invoice.Type.DEBIT),
            name=kwargs.get("name", "Inv"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("0.00")),
            value_open=kwargs.get("value_open", Decimal("0.00")),
            value_closed=kwargs.get("value_closed", Decimal("0.00")),
            user=self.user,
            contract=kwargs.get("contract"),
        )

    def _create_payment(self, **kwargs):
        return Payment.objects.create(
            status=kwargs.get("status", Payment.STATUS_OPEN),
            type=kwargs.get("type", Payment.TYPE_DEBIT),
            name=kwargs.get("name", "Pay"),
            description=kwargs.get("description", ""),
            reference=kwargs.get("reference", "ref"),
            date=kwargs.get("date", date(2026, 1, 1)),
            installments=kwargs.get("installments", 1),
            payment_date=kwargs.get("payment_date", date(2026, 1, 2)),
            fixed=kwargs.get("fixed", False),
            active=kwargs.get("active", True),
            value=kwargs.get("value", Decimal("10.00")),
            invoice=kwargs.get("invoice"),
            user=kwargs.get("user", self.user),
        )

    def test_oneoff_20250111_migrate_model_inserts_all_rows(self):
        command = cmd_migrate_model.Command()
        cursor = MagicMock()
        cursor_cm = MagicMock()
        cursor_cm.__enter__.return_value = cursor

        with patch("financial.management.commands.ONEOFF_20250111_MIGRATE_MODEL.connection.cursor", return_value=cursor_cm):
            command.run_command()

        self.assertEqual(cursor.execute.call_count, 4)

    def test_oneoff_20231003_update_home_payment_date_updates_sequence(self):
        command = cmd_update_home_date.Command()
        p1 = SimpleNamespace(payment_date=None, value=None, save=MagicMock())
        p2 = SimpleNamespace(payment_date=None, value=None, save=MagicMock())
        invoice = SimpleNamespace(payment_set=SimpleNamespace(all=MagicMock(return_value=[p1, p2])))
        query = MagicMock()
        query.first.return_value = invoice

        with patch("financial.management.commands.ONEOFF_20231003_UPDATE_FINANCIAL_HOME_PAYMENT_DATE.Invoice.objects.filter", return_value=query):
            command.run_command()

        self.assertEqual(p1.payment_date, "2023-11-06")
        self.assertEqual(p2.payment_date, "2023-12-06")
        self.assertEqual(p1.value, 1206.58)
        self.assertEqual(p2.value, 1206.58)
        self.assertTrue(p1.save.called and p2.save.called)

    def test_oneoff_20231006_update_financing_value_respects_thresholds(self):
        command = cmd_update_financing.Command()
        payments = []
        for installment in [67, 68, 87, 147, 207, 267, 327, 387]:
            payments.append(SimpleNamespace(installments=installment, value=0, save=MagicMock()))
        query = MagicMock()
        query.order_by.return_value.all.return_value = payments

        with patch("financial.management.commands.ONEOFF_20231006_UPDATE_FINANCING_VALUE.Payment.objects.filter", return_value=query):
            command.run_command()

        self.assertFalse(payments[0].save.called)
        self.assertEqual(payments[1].value, 1209.85)
        self.assertEqual(payments[-1].value, 1236.86)
        self.assertTrue(all(p.save.called for p in payments[1:]))

    def test_oneoff_20260104_update_payment_date_updates_all_found_ids(self):
        command = cmd_update_payment_date.Command()
        p1 = SimpleNamespace(payment_date=None, save=MagicMock())
        p2 = SimpleNamespace(payment_date=None, save=MagicMock())
        query = MagicMock()
        query.all.return_value = [p1, p2]

        with patch("financial.management.commands.ONEOFF_20260104_UPDATE_PAYMENT_DATE.Payment.objects.filter", return_value=query):
            command.run_command()

        self.assertEqual(p1.payment_date, "2026-01-18")
        self.assertEqual(p2.payment_date, "2026-01-18")
        self.assertTrue(p1.save.called and p2.save.called)

    def test_oneoff_20260104_fix_payment_reference_updates_specific_fields(self):
        command = cmd_fix_reference.Command()
        payment_map = {pid: SimpleNamespace(description=None, reference=None, payment_date=None, save=MagicMock()) for pid in [2066, 2067, 2068, 2069, 1979, 1980, 1981, 1982]}

        def _filter_side_effect(*args, **kwargs):
            pid = kwargs["id"]
            return SimpleNamespace(first=lambda: payment_map[pid])

        with patch("financial.management.commands.ONEOFF_20260104_FIX_PAYMENT_REFERENCE.Payment.objects.filter", side_effect=_filter_side_effect):
            command.run_command()

        self.assertEqual(payment_map[2066].description, "")
        self.assertEqual(payment_map[2068].payment_date, "2025-12-18")
        self.assertEqual(payment_map[1981].payment_date, "2025-12-18")
        self.assertTrue(all(p.save.called for p in payment_map.values()))

    def test_oneoff_20251106_contract_to_tag_creates_tag_and_links_invoice(self):
        command = cmd_contract_to_tag.Command()
        contract = SimpleNamespace(name="Contract A", user=self.user)
        tag = SimpleNamespace(id=99, name="Contract A")
        invoice_with_add = SimpleNamespace(
            name="Inv A",
            tags=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(exists=lambda: False), add=MagicMock()),
        )
        invoice_without_add = SimpleNamespace(
            name="Inv B",
            tags=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(exists=lambda: True), add=MagicMock()),
        )

        with patch("financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Contract.objects.all", return_value=[contract]), patch(
            "financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Tag.objects.get_or_create",
            return_value=(tag, True),
        ), patch(
            "financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Invoice.objects.filter",
            return_value=[invoice_with_add, invoice_without_add],
        ), patch("financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.random.randint", return_value=0):
            command.run_command()

        self.assertTrue(invoice_with_add.tags.add.called)
        self.assertFalse(invoice_without_add.tags.add.called)

    def test_oneoff_20251106_contract_to_tag_handles_existing_tag(self):
        command = cmd_contract_to_tag.Command()
        contract = SimpleNamespace(name="Contract B", user=self.user)
        tag = SimpleNamespace(id=100, name="Contract B")
        invoice = SimpleNamespace(name="Inv B", tags=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(exists=lambda: True), add=MagicMock()))

        with patch("financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Contract.objects.all", return_value=[contract]), patch(
            "financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Tag.objects.get_or_create",
            return_value=(tag, False),
        ), patch(
            "financial.management.commands.ONEOFF_20251106_CONTRACT_TO_TAG.Invoice.objects.filter",
            return_value=[invoice],
        ), patch("builtins.print"):
            command.run_command()

        self.assertFalse(invoice.tags.add.called)

    def test_oneoff_20220910_generate_invoice_assigns_existing_and_fixed_paths(self):
        command = cmd_generate_invoice.Command()
        existing_invoice = SimpleNamespace(
            contract="existing-contract",
            value=Decimal("10.00"),
            value_open=Decimal("10.00"),
            value_closed=Decimal("0.00"),
            installments=1,
            save=MagicMock(),
        )
        first_invoice = SimpleNamespace(save=MagicMock())
        fixed_invoice = SimpleNamespace(save=MagicMock())
        created_contract = SimpleNamespace(save=MagicMock())
        payment_new = SimpleNamespace(
            name="A",
            status=Payment.STATUS_OPEN,
            value=Decimal("5.00"),
            type=Payment.TYPE_DEBIT,
            date=date(2026, 1, 1),
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            invoice=None,
            save=MagicMock(),
        )
        payment_fixed = SimpleNamespace(
            name="A",
            status=Payment.STATUS_DONE,
            value=Decimal("7.00"),
            type=Payment.TYPE_DEBIT,
            date=date(2026, 1, 1),
            payment_date=date(2026, 1, 2),
            fixed=True,
            active=True,
            invoice=None,
            save=MagicMock(),
        )
        payment_existing = SimpleNamespace(
            name="A",
            status=Payment.STATUS_DONE,
            value=Decimal("3.00"),
            type=Payment.TYPE_DEBIT,
            date=date(2026, 1, 1),
            payment_date=date(2026, 1, 2),
            fixed=False,
            active=True,
            invoice=None,
            save=MagicMock(),
        )
        payments = [payment_new, payment_fixed, payment_existing]

        invoice_mock = MagicMock(side_effect=[first_invoice, fixed_invoice])
        invoice_mock.objects.filter.side_effect = [
            SimpleNamespace(first=lambda: None),
            SimpleNamespace(first=lambda: existing_invoice),
            SimpleNamespace(first=lambda: existing_invoice),
        ]

        with patch("financial.management.commands.ONEOFF_20220910_GENERATE_INVOICE.Payment.objects.all") as mocked_payments_all, patch(
            "financial.management.commands.ONEOFF_20220910_GENERATE_INVOICE.Contract",
            return_value=created_contract,
        ), patch("financial.management.commands.ONEOFF_20220910_GENERATE_INVOICE.Invoice", invoice_mock):
            mocked_payments_all.return_value.order_by.return_value = payments
            command.run_command()

        self.assertTrue(created_contract.save.called)
        self.assertTrue(first_invoice.save.called)
        self.assertTrue(fixed_invoice.save.called)
        self.assertEqual(existing_invoice.value, Decimal("13.00"))
        self.assertEqual(existing_invoice.value_closed, Decimal("3.00"))
        self.assertEqual(existing_invoice.installments, 2)

    def test_cron_recalculate_invoices_handles_no_payments_invalid_and_valid(self):
        command = cmd_recalculate.Command()
        invoice_no_payment = self._create_invoice(name="No payment", active=True, value=Decimal("10.00"), value_open=Decimal("10.00"))
        invoice_invalid = self._create_invoice(name="Invalid", value=Decimal("0.00"), value_open=Decimal("0.00"), value_closed=Decimal("0.00"))
        invoice_valid = self._create_invoice(name="Valid", value=Decimal("0.00"), value_open=Decimal("0.00"), value_closed=Decimal("0.00"))

        tag = Tag.objects.create(name="Budget", color="#123456", user=self.user)
        Budget.objects.create(tag=tag, user=self.user, allocation_percentage=Decimal("10.00"))
        invoice_valid.tags.add(tag)

        self._create_payment(invoice=invoice_invalid, status=Payment.STATUS_OPEN, value=Decimal("20.00"), active=True)
        self._create_payment(invoice=invoice_valid, status=Payment.STATUS_OPEN, value=Decimal("40.00"), payment_date=date(2026, 1, 5), active=True)
        self._create_payment(invoice=invoice_valid, status=Payment.STATUS_DONE, value=Decimal("60.00"), payment_date=date(2026, 1, 3), active=True)

        with patch("builtins.print"):
            command.run_command()

        invoice_no_payment.refresh_from_db()
        invoice_invalid.refresh_from_db()
        invoice_valid.refresh_from_db()

        self.assertFalse(invoice_no_payment.active)
        self.assertEqual(invoice_invalid.value, Decimal("0.00"))
        self.assertEqual(invoice_valid.value, Decimal("100.00"))
        self.assertEqual(invoice_valid.value_open, Decimal("40.00"))
        self.assertEqual(invoice_valid.value_closed, Decimal("60.00"))
        self.assertEqual(invoice_valid.payment_date, date(2026, 1, 5))

    def test_cron_payment_discord_send_discord_and_run_command(self):
        command = cmd_discord.Command()
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1, Payment.TYPE_DEBIT, "Pay 1", "2026-01-01", Decimal("12.34"))]
        cursor_cm = MagicMock()
        cursor_cm.__enter__.return_value = cursor

        with patch("financial.management.commands.cron_payment_discord.connection.cursor", return_value=cursor_cm), patch(
            "financial.management.commands.cron_payment_discord.requests.post"
        ) as mocked_post:
            command.send_discord(date(2026, 1, 3))

        self.assertTrue(mocked_post.called)
        sent_json = mocked_post.call_args.kwargs["json"]
        self.assertEqual(sent_json["data"][0]["id"], 1)
        self.assertEqual(sent_json["data"][0]["payment_date"], "01/01/2026")

        with patch.object(command, "send_discord") as mocked_send, patch(
            "financial.management.commands.cron_payment_discord.datetime"
        ) as mocked_datetime, patch("builtins.print"):
            mocked_datetime.now.return_value.date.return_value = date(2026, 1, 1)
            command.run_command()

        mocked_send.assert_called_once_with(date(2026, 1, 4))

    def test_cron_payment_email_send_email_and_run_command_paths(self):
        command = cmd_email.Command()
        user = User.objects.create_user(username="email-user", email="email-user@test.com", password="123")
        invoice = self._create_invoice(name="Email invoice")
        self._create_payment(invoice=invoice, user=user, status=Payment.STATUS_OPEN, active=True, value=Decimal("30.00"))

        with patch("financial.management.commands.cron_payment_email.render_to_string", return_value="<html/>"), patch(
            "financial.management.commands.cron_payment_email.SMTP"
        ) as mocked_smtp:
            smtp_instance = mocked_smtp.return_value.__enter__.return_value
            result = command.send_email_to_user(user, date(2026, 1, 3))
        self.assertTrue(result)
        self.assertTrue(smtp_instance.send_message.called)

        with patch("financial.management.commands.cron_payment_email.SMTP", side_effect=Exception("smtp-down")), patch(
            "financial.management.commands.cron_payment_email.render_to_string", return_value="<html/>"
        ):
            self.assertFalse(command.send_email_to_user(user, date(2026, 1, 3)))

        with patch("financial.management.commands.cron_payment_email.User.objects.filter") as mocked_users, patch(
            "builtins.print"
        ), patch.object(command, "send_email_to_user", return_value=True) as mocked_send, patch(
            "financial.management.commands.cron_payment_email.datetime"
        ) as mocked_datetime:
            mocked_datetime.now.return_value.date.return_value = date(2026, 1, 1)
            users_qs = MagicMock()
            users_qs.exists.return_value = True
            users_qs.count.return_value = 2
            users_qs.__iter__.return_value = iter([user, User(username="no-mail", email="")])
            mocked_users.return_value.distinct.return_value = users_qs
            command.run_command()

        self.assertEqual(mocked_send.call_count, 1)

    def test_cron_payment_email_no_payments_and_error_count_path(self):
        command = cmd_email.Command()
        user_without_payments = User.objects.create_user(username="no-payments", email="no-payments@test.com", password="123")
        self.assertFalse(command.send_email_to_user(user_without_payments, date(2026, 1, 3)))

        user_with_email = User.objects.create_user(username="with-email", email="with-email@test.com", password="123")
        user_without_email = User.objects.create_user(username="without-email", email="", password="123")
        users_qs = MagicMock()
        users_qs.exists.return_value = True
        users_qs.count.return_value = 2
        users_qs.__iter__.return_value = iter([user_with_email, user_without_email])

        with patch("financial.management.commands.cron_payment_email.User.objects.filter") as mocked_users, patch.object(
            command, "send_email_to_user", return_value=False
        ) as mocked_send, patch("financial.management.commands.cron_payment_email.datetime") as mocked_datetime, patch(
            "builtins.print"
        ):
            mocked_datetime.now.return_value.date.return_value = date(2026, 1, 1)
            mocked_users.return_value.distinct.return_value = users_qs
            command.run_command()

        mocked_send.assert_called_once()

    def test_cron_payment_email_run_command_with_no_users(self):
        command = cmd_email.Command()
        users_qs = MagicMock()
        users_qs.exists.return_value = False

        with patch("financial.management.commands.cron_payment_email.User.objects.filter") as mocked_users, patch(
            "financial.management.commands.cron_payment_email.datetime"
        ) as mocked_datetime, patch("builtins.print"):
            mocked_datetime.now.return_value.date.return_value = date(2026, 1, 1)
            mocked_users.return_value.distinct.return_value = users_qs
            command.run_command()

    def test_handle_methods_call_run_command(self):
        commands = [
            cmd_generate_invoice.Command(),
            cmd_update_home_date.Command(),
            cmd_update_financing.Command(),
            cmd_migrate_model.Command(),
            cmd_contract_to_tag.Command(),
            cmd_fix_reference.Command(),
            cmd_update_payment_date.Command(),
            cmd_discord.Command(),
            cmd_email.Command(),
            cmd_recalculate.Command(),
        ]
        for command in commands:
            with patch.object(command, "run_command") as mocked_run, patch("builtins.print"), patch.object(
                command.stdout, "write"
            ):
                command.handle()
            self.assertTrue(mocked_run.called)

    def test_process_imported_helpers_cover_remaining_merge_paths(self):
        command = cmd_process_imported.Command()

        with patch.object(command, "get_merge_group_payments", return_value=[SimpleNamespace(id=1), SimpleNamespace(id=2)]), patch.object(
            command, "try_set_processing", side_effect=[False, True]
        ):
            claimed = command.claim_merge_group_payments("g1")
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0].id, 2)

        self.assertEqual(command.generate_payment_installments_by_name("Compra 2/5"), (2, 5))

        source_tags = [SimpleNamespace(id=2), SimpleNamespace(id=3)]
        target_tags = [SimpleNamespace(id=2)]
        merged = command.merge_tags(source_tags, target_tags)
        self.assertEqual([tag.id for tag in merged], [2, 3])

        payment = SimpleNamespace(
            description="",
            reference="",
            date=None,
            payment_date=None,
            save=MagicMock(),
        )
        main_payment = SimpleNamespace(reference="ref", raw_date=date(2026, 1, 1), raw_payment_date=date(2026, 1, 2))
        with patch.object(command, "get_main_payment", return_value=main_payment), patch.object(
            command, "get_payment_description", return_value="desc"
        ):
            command.update_invoice_by_imported_payment(payment, [SimpleNamespace()])
        self.assertEqual(payment.reference, "ref")
        self.assertEqual(payment.description, "desc")
        self.assertTrue(payment.save.called)

        with self.assertRaisesMessage(Exception, "Pagamento merge sem pagamento selecionado"):
            command.update_invoice_by_imported_payment(None, [SimpleNamespace()])

        merge_item = SimpleNamespace(matched_payment=payment)
        with patch.object(command, "update_invoice_by_imported_payment") as mocked_update:
            command.process_payment_by_merge([merge_item])
        mocked_update.assert_called_once()

        with patch.object(command, "check_payment_is_merge", return_value=True), patch.object(
            command, "process_payment_by_merge"
        ) as mocked_merge, patch.object(command, "finish_with_success") as mocked_success:
            command.process_payment([SimpleNamespace()])
        self.assertTrue(mocked_merge.called)
        self.assertTrue(mocked_success.called)

        with patch.object(command, "is_processing_running", return_value=True), patch("builtins.print") as mocked_print:
            command.run_command()
        self.assertTrue(mocked_print.called)
