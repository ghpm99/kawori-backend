from django.core.management.base import BaseCommand

from kawori.version import __version__


class Command(BaseCommand):
    help = "Print the current application version."

    def handle(self, *args, **options):
        self.stdout.write(__version__)
