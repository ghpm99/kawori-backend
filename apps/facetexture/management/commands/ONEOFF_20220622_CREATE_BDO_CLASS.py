import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass


class Command(BaseCommand):
    """
        Create Bdo Class
    """

    def run_command(self):

        classes = [
            {
                'name': 'Warrior',
                'abbreviation': 'Guerreiro',
                'image': 'bdoclass/warrior.png',
                'class_image': 'classimage/warrior.png',
            },
            {
                'name': 'Ranger',
                'abbreviation': 'Caçadora',
                'image': 'bdoclass/ranger.png',
                'class_image': 'classimage/ranger.png',
            },
            {
                'name': 'Sorceress',
                'abbreviation': 'Feiticeira',
                'image': 'bdoclass/sorceress.png',
                'class_image': 'classimage/sorceress.png',
            },
            {
                'name': 'Berserker',
                'abbreviation': 'Berserker',
                'image': 'bdoclass/berserker.png',
                'class_image': 'classimage/berserker.png',
            },
            {
                'name': 'Tamer',
                'abbreviation': 'Domadora',
                'image': 'bdoclass/tamer.png',
                'class_image': 'classimage/tamer.png',
            },
            {
                'name': 'Musa',
                'abbreviation': 'Musa',
                'image': 'bdoclass/musa.png',
                'class_image': 'classimage/musa.png',
            },
            {
                'name': 'Maehwa',
                'abbreviation': 'Maehwa',
                'image': 'bdoclass/maehwa.png',
                'class_image': 'classimage/maehwa.png',
            },
            {
                'name': 'Valkyrie',
                'abbreviation': 'Valquiria',
                'image': 'bdoclass/valkyrie.png',
                'class_image': 'classimage/valkyrie.png',
            },
            {
                'name': 'Kunoichi',
                'abbreviation': 'Kunoichi',
                'image': 'bdoclass/kunoichi.png',
                'class_image': 'classimage/kunoichi.png',
            },
            {
                'name': 'Ninja',
                'abbreviation': 'Ninja',
                'image': 'bdoclass/ninja.png',
                'class_image': 'classimage/ninja.png',
            },
            {
                'name': 'Wizard',
                'abbreviation': 'Mago',
                'image': 'bdoclass/wizard.png',
                'class_image': 'classimage/wizard.png',
            },
            {
                'name': 'Witch',
                'abbreviation': 'Bruxa',
                'image': 'bdoclass/witch.png',
                'class_image': 'classimage/witch.png',
            },
            {
                'name': 'Dark Knight',
                'abbreviation': 'Cavaleira das Trevas',
                'image': 'bdoclass/dark_knight.png',
                'class_image': 'classimage/dark_knight.png',
            },
            {
                'name': 'Striker',
                'abbreviation': 'Lutador',
                'image': 'bdoclass/striker.png',
                'class_image': 'classimage/striker.png',
            },
            {
                'name': 'Mystic',
                'abbreviation': 'Mistica',
                'image': 'bdoclass/mystic.png',
                'class_image': 'classimage/mystic.png',
            },
            {
                'name': 'Archer',
                'abbreviation': 'Arqueiro',
                'image': 'bdoclass/archer.png',
                'class_image': 'classimage/archer.png',
            },
            {
                'name': 'Lahn',
                'abbreviation': 'Lahn',
                'image': 'bdoclass/lahn.png',
                'class_image': 'classimage/lahn.png',
            },
            {
                'name': 'Shai',
                'abbreviation': 'Shai',
                'image': 'bdoclass/shai.png',
                'class_image': 'classimage/shai.png',
            },
            {
                'name': 'Guardian',
                'abbreviation': 'Guardia',
                'image': 'bdoclass/guardian.png',
                'class_image': 'classimage/guardian.png',
            },
            {
                'name': 'Hashashin',
                'abbreviation': 'Hashashin',
                'image': 'bdoclass/hashashin.png',
                'class_image': 'classimage/hashashin.png',
            },
            {
                'name': 'Nova',
                'abbreviation': 'Nova',
                'image': 'bdoclass/nova.png',
                'class_image': 'classimage/nova.png',
            },
            {
                'name': 'Sage',
                'abbreviation': 'Sage',
                'image': 'bdoclass/sage.png',
                'class_image': 'classimage/sage.png',
            },
            {
                'name': 'Corsair',
                'abbreviation': 'Corsaria',
                'image': 'bdoclass/corsair.png',
                'class_image': 'classimage/corsair.png',
            },
            {
                'name': 'Drakania',
                'abbreviation': 'Drakania',
                'image': 'bdoclass/drakania.png',
                'class_image': 'classimage/drakania.png',
            }
        ]

        for classe in classes:
            exists_class = BDOClass.objects.filter(
                name=classe['name']).first()

            if exists_class is not None:
                exists_class.abbreviation = classe['abbreviation']
                exists_class.image = classe['image']
                exists_class.class_image = classe['class_image']
                exists_class.save()
                print(f'{classe["name"]} atualizado')
                continue

            BDOClass.objects.create(
                name=classe['name'],
                abbreviation=classe['abbreviation'],
                image=classe['image'],
                class_image=classe['class_image']
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
