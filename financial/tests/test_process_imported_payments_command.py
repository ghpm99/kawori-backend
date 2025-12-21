from django.core.management import call_command

from django.test import TestCase


class ProcessImportedPaymentsCommandTest(TestCase):
    def test_command_runs_without_errors(self):
        call_command("process_imported_payments")
