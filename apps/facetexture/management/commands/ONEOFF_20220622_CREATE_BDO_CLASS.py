import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass


class Command(BaseCommand):
    """
        Create Bdo Class
    """

    def run_command(self):

        classes = [
            {'name': 'Warrior', 'abbreviation': 'Guerreiro'},
            {'name': 'Ranger', 'abbreviation': 'Caçadora'},
            {'name': 'Sorceress', 'abbreviation': 'Feiticeira'},
            {'name': 'Berserker', 'abbreviation': 'Berserker'},
            {'name': 'Tamer', 'abbreviation': 'Domadora'},
            {'name': 'Musa', 'abbreviation': 'Musa'},
            {'name': 'Maehwa', 'abbreviation': 'Maehwa'},
            {'name': 'Valkyrie', 'abbreviation': 'Valquiria'},
            {'name': 'Kunoichi', 'abbreviation': 'Kunoichi'},
            {'name': 'Ninja', 'abbreviation': 'Ninja'},
            {'name': 'Wizard', 'abbreviation': 'Mago'},
            {'name': 'Witch', 'abbreviation': 'Bruxa'},
            {'name': 'Dark Knight', 'abbreviation': 'Cavaleira das Trevas'},
            {'name': 'Striker', 'abbreviation': 'Lutador'},
            {'name': 'Mystic', 'abbreviation': 'Mistica'},
            {'name': 'Archer', 'abbreviation': 'Arqueiro'},
            {'name': 'Lahn', 'abbreviation': 'Lahn'},
            {'name': 'Shai', 'abbreviation': 'Shai'},
            {'name': 'Guardian', 'abbreviation': 'Guardia'},
            {'name': 'Hashashin', 'abbreviation': 'Hashashin'},
            {'name': 'Nova', 'abbreviation': 'Nova'},
            {'name': 'Sage', 'abbreviation': 'Sage'},
            {'name': 'Corsair', 'abbreviation': 'Corsaria'},
            {'name': 'Drakania', 'abbreviation': 'Drakania'}
        ]

        for classe in classes:
            exists_class = BDOClass.objects.filter(name=classe['name']).exists()

            if exists_class:
                print(f'{classe["name"]} ja existe')
                continue

            BDOClass.objects.create(
                name=classe['name'],
                abbreviation=classe['abbreviation']
            )
            print(f'{classe["name"]} criado com sucesso')

        print('Classes criadas!')

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
