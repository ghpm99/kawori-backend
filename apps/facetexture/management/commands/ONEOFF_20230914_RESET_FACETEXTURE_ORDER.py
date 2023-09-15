import time
from django.core.management.base import BaseCommand
from facetexture.models import Character
from django.contrib.auth.models import User


class Command(BaseCommand):
    """
        Reset facetexture order
    """

    def run_command(self):

        user_list = User.objects.order_by('id').all()

        for user in user_list:
            character_list = Character.objects.filter(active=True, user=user).order_by('order').all()
            for index, character in enumerate(character_list):
                character.order = index
                character.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
