import time
from django.core.management.base import BaseCommand
from facetexture.models import PreviewBackground


class Command(BaseCommand):
    """
        Create Preview Background
    """

    def run_command(self):
        background = PreviewBackground.objects.filter(id=1).first()

        if not background:
            PreviewBackground.objects.create(
                image='background/background.png'
            )
            print('Background criado com sucesso!')
        else:
            background.image = 'background/background.png'
            print('Background atualizado com sucesso!')

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
