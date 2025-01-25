import time
from django.core.management.base import BaseCommand
from facetexture.models import BDOClass, Character
from django.contrib.auth.models import User


class Command(BaseCommand):
    """
        Reset facetexture order
    """

    def run_command(self):

        bdo_class_list = BDOClass.objects.all()

        for bdo_class in bdo_class_list:
            match bdo_class.name:
                case 'Warrior':
                    bdo_class.class_order = 1
                case 'Dark Knight':
                    bdo_class.class_order = 13
                case 'Striker':
                    bdo_class.class_order = 14
                case 'Mystic':
                    bdo_class.class_order = 15
                case 'Archer':
                    bdo_class.class_order = 17
                case 'Lahn':
                    bdo_class.class_order = 16
                case 'Shai':
                    bdo_class.class_order = 18
                case 'Guardian':
                    bdo_class.class_order = 19
                case 'Hashashin':
                    bdo_class.class_order = 20
                case 'Nova':
                    bdo_class.class_order = 21
                case 'Sage':
                    bdo_class.class_order = 22
                case 'Corsair':
                    bdo_class.class_order = 23
                case 'Drakania':
                    bdo_class.class_order = 24
                case 'Maegu':
                    bdo_class.class_order = 26
                case 'Woosa':
                    bdo_class.class_order = 25
                case 'Scholar':
                    bdo_class.class_order = 27
                case 'Dosa':
                    bdo_class.class_order = 28
                case 'Ranger':
                    bdo_class.class_order = 2
                case 'Sorceress':
                    bdo_class.class_order = 3
                case 'Berserker':
                    bdo_class.class_order = 4
                case 'Tamer':
                    bdo_class.class_order = 5
                case 'Musa':
                    bdo_class.class_order = 6
                case 'Maehwa':
                    bdo_class.class_order = 7
                case 'Valkyrie':
                    bdo_class.class_order = 8
                case 'Kunoichi':
                    bdo_class.class_order = 9
                case 'Ninja':
                    bdo_class.class_order = 10
                case 'Wizard':
                    bdo_class.class_order = 11
                case 'Witch':
                    bdo_class.class_order = 12
            bdo_class.save()


    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS('Running...'))

        self.run_command()

        self.stdout.write(self.style.SUCCESS('Success! :)'))
        self.stdout.write(self.style.SUCCESS(
            f'Done with {time.time() - begin}s'))
