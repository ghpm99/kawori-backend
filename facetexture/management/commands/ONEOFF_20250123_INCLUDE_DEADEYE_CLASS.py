import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass, Character
from django.contrib.auth.models import User


class Command(BaseCommand):
    """
        Cadastrar a classe Dead Eye
    """

    def run_command(self):

        dead_eye_class = BDOClass(name="Dead Eye", abbreviation="Dead Eye", color="#9f7362", class_order=29)
        dead_eye_class.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
