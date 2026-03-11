from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test helper command that always fails."

    def handle(self, *args, **options):
        raise CommandError("intentional failure")
