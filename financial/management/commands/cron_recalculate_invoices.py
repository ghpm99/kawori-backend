import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Case, Count, F, Sum, When

from contract.models import Contract
from invoice.models import Invoice
from payment.models import Payment


class Command(BaseCommand):
    help = "Validates and reports inconsistencies in invoices, payments, and contracts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Automatically fix inconsistencies (recalculate values and deactivate invalid invoices)",
        )

    def handle(self, *args, **options):
        begin = time.time()
        self.fix_mode = options["fix"]
        self.issues = []

        self.stdout.write("Running financial health check...\n")

        if self.fix_mode:
            self.stdout.write("FIX MODE enabled — inconsistencies will be corrected.\n")

        self.check_invoices()
        self.check_contracts()
        self.check_orphan_payments()

        self.stdout.write(f"\n{'=' * 60}")
        if self.issues:
            self.stdout.write(f"Found {len(self.issues)} issue(s):\n")
            for issue in self.issues:
                self.stdout.write(f"  - {issue}")
        else:
            self.stdout.write("No issues found.")

        self.stdout.write(f"\nDone in {time.time() - begin:.2f}s")

    def report(self, msg):
        self.issues.append(msg)
        self.stdout.write(f"[ISSUE] {msg}")

    def check_invoices(self):
        invoices = (
            Invoice.objects.filter(active=True)
            .select_related("contract", "user")
            .iterator(chunk_size=1000)
        )

        for invoice in invoices:
            self.check_invoice(invoice)

    def check_invoice(self, invoice):
        prefix = f"Invoice {invoice.id} (user={invoice.user_id})"
        payments = Payment.objects.filter(invoice=invoice, active=True)

        agg = payments.aggregate(
            total=Sum("value"),
            value_open=Sum(
                Case(
                    When(status=Payment.STATUS_OPEN, then=F("value")),
                    default=Decimal("0.00"),
                )
            ),
            value_closed=Sum(
                Case(
                    When(status=Payment.STATUS_DONE, then=F("value")),
                    default=Decimal("0.00"),
                )
            ),
            count=Count("id"),
        )

        payment_count = agg["count"]
        expected_value = agg["total"] or Decimal("0.00")
        expected_value_open = agg["value_open"] or Decimal("0.00")
        expected_value_closed = agg["value_closed"] or Decimal("0.00")

        # 1. Invoice without payments
        if payment_count == 0:
            self.report(f"{prefix}: no active payments found")
            if self.fix_mode:
                invoice.active = False
                invoice.save()
                self.stdout.write(f"  [FIX] Deactivated invoice {invoice.id}")
            return

        # 2. Invoice without tags
        if not invoice.tags.exists():
            self.report(f"{prefix}: no tags assigned")

        # 3. Invoice without budget tag
        if not invoice.tags.filter(budget__isnull=False).exists():
            self.report(f"{prefix}: no budget tag assigned")

        # 4. Value mismatch (invoice.value != sum of payments)
        if invoice.value != expected_value:
            self.report(
                f"{prefix}: value mismatch — "
                f"invoice.value={invoice.value}, sum(payments)={expected_value}"
            )
            if self.fix_mode:
                invoice.value = expected_value
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} value to {expected_value}"
                )

        # 5. value_open mismatch
        if invoice.value_open != expected_value_open:
            self.report(
                f"{prefix}: value_open mismatch — "
                f"invoice.value_open={invoice.value_open}, sum(open payments)={expected_value_open}"
            )
            if self.fix_mode:
                invoice.value_open = expected_value_open
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} value_open to {expected_value_open}"
                )

        # 6. value_closed mismatch
        if invoice.value_closed != expected_value_closed:
            self.report(
                f"{prefix}: value_closed mismatch — "
                f"invoice.value_closed={invoice.value_closed}, sum(done payments)={expected_value_closed}"
            )
            if self.fix_mode:
                invoice.value_closed = expected_value_closed
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} value_closed to {expected_value_closed}"
                )

        # 7. value != value_open + value_closed (after potential fixes above)
        current_value = invoice.value if not self.fix_mode else expected_value
        current_open = invoice.value_open if not self.fix_mode else expected_value_open
        current_closed = (
            invoice.value_closed if not self.fix_mode else expected_value_closed
        )
        if current_value != (current_open + current_closed):
            self.report(
                f"{prefix}: value decomposition error — "
                f"value={current_value} != value_open({current_open}) + value_closed({current_closed})"
            )

        # 8. Installments count mismatch
        if invoice.installments != payment_count:
            self.report(
                f"{prefix}: installments mismatch — "
                f"invoice.installments={invoice.installments}, active payments={payment_count}"
            )

        # 9. Payment date consistency
        next_open_payment = (
            payments.filter(status=Payment.STATUS_OPEN)
            .order_by("payment_date")
            .values_list("payment_date", flat=True)
            .first()
        )

        if invoice.status == Invoice.STATUS_OPEN and next_open_payment is None:
            self.report(f"{prefix}: status is OPEN but no open payments exist")
            if self.fix_mode:
                invoice.status = Invoice.STATUS_DONE
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} status to DONE"
                )

        if next_open_payment and invoice.payment_date != next_open_payment:
            self.report(
                f"{prefix}: payment_date mismatch — "
                f"invoice.payment_date={invoice.payment_date}, next open payment={next_open_payment}"
            )
            if self.fix_mode:
                invoice.payment_date = next_open_payment
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} payment_date to {next_open_payment}"
                )

        if invoice.payment_date is None and invoice.status == Invoice.STATUS_OPEN:
            self.report(f"{prefix}: payment_date is null but status is OPEN")

        # 10. Status consistency
        if (
            expected_value_open == Decimal("0.00")
            and invoice.status == Invoice.STATUS_OPEN
        ):
            self.report(f"{prefix}: all payments are done but invoice status is OPEN")
            if self.fix_mode:
                invoice.status = Invoice.STATUS_DONE
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} status to DONE"
                )

        if (
            expected_value_open > Decimal("0.00")
            and invoice.status == Invoice.STATUS_DONE
        ):
            self.report(f"{prefix}: has open payments but invoice status is DONE")
            if self.fix_mode:
                invoice.status = Invoice.STATUS_OPEN
                self.stdout.write(
                    f"  [FIX] Updated invoice {invoice.id} status to OPEN"
                )

        # 11. Payment type mismatch with invoice
        mismatched_type_count = payments.exclude(type=invoice.type).count()
        if mismatched_type_count > 0:
            self.report(
                f"{prefix}: {mismatched_type_count} payment(s) have different type than invoice (invoice.type={invoice.type})"
            )

        # 12. Payment user mismatch
        wrong_user_count = payments.exclude(user=invoice.user).count()
        if wrong_user_count > 0:
            self.report(
                f"{prefix}: {wrong_user_count} payment(s) belong to a different user than the invoice"
            )

        # 13. Payment with negative or zero value
        invalid_value_count = payments.filter(value__lte=0).count()
        if invalid_value_count > 0:
            self.report(f"{prefix}: {invalid_value_count} payment(s) with value <= 0")

        if self.fix_mode:
            invoice.save()

    def check_contracts(self):
        contracts = Contract.objects.all().iterator(chunk_size=1000)

        for contract in contracts:
            prefix = f"Contract {contract.id} (user={contract.user_id})"

            agg = Invoice.objects.filter(contract=contract, active=True).aggregate(
                total=Sum("value"),
                value_open=Sum("value_open"),
                value_closed=Sum("value_closed"),
                count=Count("id"),
            )

            expected_value = agg["total"] or Decimal("0.00")
            expected_open = agg["value_open"] or Decimal("0.00")
            expected_closed = agg["value_closed"] or Decimal("0.00")

            if contract.value != expected_value:
                self.report(
                    f"{prefix}: value mismatch — "
                    f"contract.value={contract.value}, sum(invoices)={expected_value}"
                )
                if self.fix_mode:
                    contract.value = expected_value
                    self.stdout.write(
                        f"  [FIX] Updated contract {contract.id} value to {expected_value}"
                    )

            if contract.value_open != expected_open:
                self.report(
                    f"{prefix}: value_open mismatch — "
                    f"contract.value_open={contract.value_open}, sum(invoices)={expected_open}"
                )
                if self.fix_mode:
                    contract.value_open = expected_open
                    self.stdout.write(
                        f"  [FIX] Updated contract {contract.id} value_open to {expected_open}"
                    )

            if contract.value_closed != expected_closed:
                self.report(
                    f"{prefix}: value_closed mismatch — "
                    f"contract.value_closed={contract.value_closed}, sum(invoices)={expected_closed}"
                )
                if self.fix_mode:
                    contract.value_closed = expected_closed
                    self.stdout.write(
                        f"  [FIX] Updated contract {contract.id} value_closed to {expected_closed}"
                    )

            # Contract with invoices from different users
            distinct_users = (
                Invoice.objects.filter(contract=contract, active=True)
                .values("user")
                .distinct()
                .count()
            )
            if distinct_users > 1:
                self.report(
                    f"{prefix}: has invoices from {distinct_users} different users"
                )

            if self.fix_mode:
                contract.save()

    def check_orphan_payments(self):
        # Payments without invoice
        orphan_payments = Payment.objects.filter(active=True, invoice__isnull=True)
        count = orphan_payments.count()
        if count > 0:
            self.report(f"Found {count} active payment(s) without an invoice")
            for p in orphan_payments[:10]:
                self.stdout.write(
                    f"    Payment {p.id} (user={p.user_id}, value={p.value})"
                )
            if count > 10:
                self.stdout.write(f"    ... and {count - 10} more")

        # Payments linked to inactive invoices
        zombie_payments = Payment.objects.filter(active=True, invoice__active=False)
        count = zombie_payments.count()
        if count > 0:
            self.report(f"Found {count} active payment(s) linked to inactive invoices")
            for p in zombie_payments[:10]:
                self.stdout.write(
                    f"    Payment {p.id} (invoice={p.invoice_id}, user={p.user_id})"
                )
            if count > 10:
                self.stdout.write(f"    ... and {count - 10} more")
            if self.fix_mode:
                zombie_payments.update(active=False)
                self.stdout.write(f"  [FIX] Deactivated {count} zombie payments")
