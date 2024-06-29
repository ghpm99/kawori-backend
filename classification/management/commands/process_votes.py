import time

from django.core.management.base import BaseCommand

from classification.models import Answer, AnswerSummary, Path
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
            ).all()

            answer_data: dict = {}
            for answer in answer_list:
                real_vote = answer.vote * answer.height

                class_data = answer_data.get(answer.combat_style, {})

                class_data[answer.question_id] = class_data.get(answer.question_id, 0) + real_vote
                computed_answer = class_data.get('answer', [])

                computed_answer.append(answer.id)

                class_data['answer'] = computed_answer

                answer_data[answer.combat_style] = class_data

            print(answer_data)
            last_summary = AnswerSummary.objects.filter(
                bdo_class=bdo_class,
                updated_at__gte=last_path['date_path']
            ).order_by('-updated_at').first()
            if last_summary:
                last_summary.resume = answer_data
                last_summary.save()
            else:
                AnswerSummary.objects.create(
                    bdo_class=bdo_class,
                    resume=answer_data
                )

    def handle(self, *args, **options):
        begin = time.time()

        print('Running...')

        self.run_command()

        print('\nSuccess! :)')
        print(f'Done with {time.time() - begin}s')
