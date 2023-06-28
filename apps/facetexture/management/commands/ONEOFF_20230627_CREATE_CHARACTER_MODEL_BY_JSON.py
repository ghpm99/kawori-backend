import time
from django.core.management.base import BaseCommand
from facetexture.models import Facetexture, BDOClass, Character


class Command(BaseCommand):
    """
        Converte json characters to class model
    """

    def run_command(self):

        facetextures = Facetexture.objects.all()

        for facetexture_obj in facetextures:

            characters = facetexture_obj.characters['characters']

            for index, character_old in enumerate(characters):

                bdo_class = BDOClass.objects.filter(
                    id=character_old.get('class')).first()

                character = Character(
                    name=character_old.get('name'),
                    show=character_old.get('show'),
                    image=character_old.get('image'),
                    order=character_old.get(
                        'order') if character_old.get('order') else index,
                    upload=character_old.get(
                        'upload') if character_old.get('upload') else False,
                    bdoClass=bdo_class,
                    facetexture=facetexture_obj,
                )

                character.save()

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
