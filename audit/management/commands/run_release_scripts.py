from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from audit.models import (
    ReleaseScriptExecution,
    SCRIPT_STATUS_FAILURE,
    SCRIPT_STATUS_SKIPPED,
    SCRIPT_STATUS_SUCCESS,
)
from audit.release_scripts import get_pending_release_scripts


class Command(BaseCommand):
    help = "Execute pending registered release scripts up to the target version."

    def add_arguments(self, parser):
        parser.add_argument("--target-version", required=True, help="Semantic version or tag, for example v2.1.0.")
        parser.add_argument("--dry-run", action="store_true", help="List pending scripts without executing them.")
        parser.add_argument("--force", action="store_true", help="Execute scripts even if they were already recorded.")
        parser.add_argument(
            "--include-operational",
            action="store_true",
            help="Include non-oneoff registry entries such as operational commands.",
        )

    def handle(self, *args, **options):
        target_version = options["target_version"]
        dry_run = options["dry_run"]
        force = options["force"]
        include_operational = options["include_operational"]

        available_commands = get_commands()
        executed_commands = set()

        if not force:
            executed_commands = {
                (execution.release_version, execution.script_name)
                for execution in ReleaseScriptExecution.objects.filter(status=SCRIPT_STATUS_SUCCESS)
            }

        pending_scripts = get_pending_release_scripts(
            target_version=target_version,
            executed_commands=executed_commands,
            include_operational=include_operational,
        )

        if not pending_scripts:
            self.stdout.write(self.style.SUCCESS("No pending release scripts found."))
            return

        for script in pending_scripts:
            normalized_version = str(script.version)
            self.stdout.write(f"{normalized_version} -> {script.command_name}")

            if dry_run:
                continue

            if script.command_name not in available_commands:
                raise CommandError(f"Registered command not found: {script.command_name}")

            execution = ReleaseScriptExecution.objects.create(
                release_version=normalized_version,
                script_name=script.command_name,
                status=SCRIPT_STATUS_SKIPPED,
            )

            try:
                call_command(script.command_name)
            except Exception as exc:
                execution.status = SCRIPT_STATUS_FAILURE
                execution.output = str(exc)
                execution.finished_at = timezone.now()
                execution.save(update_fields=["status", "output", "finished_at"])
                raise

            execution.status = SCRIPT_STATUS_SUCCESS
            execution.output = "Executed successfully."
            execution.finished_at = timezone.now()
            execution.save(update_fields=["status", "output", "finished_at"])

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run completed."))
            return

        self.stdout.write(self.style.SUCCESS("Release scripts executed successfully."))
