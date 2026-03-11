from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test helper command for release script execution."

    def handle(self, *args, **options):
        self.stdout.write("test release script executed")
