import time

from django.core.management.base import BaseCommand
from django.db.models import Avg

from classification.models import Answer, Path
from facetexture.models import BDOClass


class Command(BaseCommand):
    help = "Process votes"

    def run_command(self):

        print('Processing votes...')
        bdo_class_list = BDOClass.objects.all()

        for bdo_class in bdo_class_list:
            print(f'Processing {bdo_class.name}...')

            last_path = Path.objects.filter(
                affected_class__overlap=[bdo_class.id]
            ).values('date_path').order_by('-date_path').first()

            filters = {
                'bdo_class': bdo_class
            }
            if last_path:
                filters['created_at__gte'] = last_path['date_path']

            answer_list = Answer.objects.filter(
                **filters
            ).values('combat_style', 'question').annotate(votes=Avg('vote'))

            class_data: dict = {}
            for answer in answer_list:
                if class_data[answer['combat_style']]:
                    class_data[answer['combat_style']] = {
                        answer['question']:  answer['votes']
                    }
                else:
                    class_data[answer['combat_style']].update({
                        answer['question']: answer['votes']
                    })
            print(class_data)

    def handle(self, *args, **options):
        begin = time.time()

        print('Running...')

        self.run_command()

        print('\nSuccess! :)')
        print(f'Done with {time.time() - begin}s')
