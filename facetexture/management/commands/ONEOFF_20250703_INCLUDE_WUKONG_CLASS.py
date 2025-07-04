import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass, Character
from django.contrib.auth.models import User


class Command(BaseCommand):
    """
        Cadastrar a classe Wukong
    """

    def run_command(self):

        dead_eye_class = BDOClass(name="Wukong", abbreviation="Wukong", color="#522424", class_order=30)
        dead_eye_class.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
