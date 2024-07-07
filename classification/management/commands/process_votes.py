import time

from django.core.management.base import BaseCommand

from classification.models import Answer, AnswerSummary, Path
from facetexture.models import BDOClass


class Command(BaseCommand):
    help = "Process votes"

    def run_command(self):
        print("Processing votes...")
        bdo_class_list = BDOClass.objects.all()

        for bdo_class in bdo_class_list:
            print(f"Processing {bdo_class.name}...")

            last_path = (
                Path.objects.filter(affected_class__overlap=[bdo_class.id])
                .values("date_path")
                .order_by("-date_path")
                .first()
            )

            filters = {"bdo_class": bdo_class}
            if last_path:
                filters["created_at__gte"] = last_path["date_path"]

            answer_list = Answer.objects.filter(**filters).all()

            answer_data: dict = {}
            for answer in answer_list:
                real_vote = answer.vote * answer.height

                class_data = answer_data.get(answer.combat_style, {})

                question_data = class_data.get(answer.question_id, {})

                total_votes = question_data.get("total_votes", 0) + 1

                computed_answer = question_data.get("answer", [])
                computed_answer.append(answer.id)

                sum_votes = question_data.get("sum_votes", 0) + real_vote

                avg_votes = sum_votes / total_votes

                question_data["total_votes"] = total_votes
                question_data["answer"] = computed_answer
                question_data["sum_votes"] = sum_votes
                question_data["avg_votes"] = avg_votes

                class_data[answer.question_id] = question_data
                answer_data[answer.combat_style] = class_data

            answer_filters = {
                "bdo_class": bdo_class,
            }
            if last_path is not None:
                answer_filters["updated_at__gte"] = last_path["date_path"]
            last_summary = (
                AnswerSummary.objects.filter(**answer_filters)
                .order_by("-updated_at")
                .first()
            )
            if last_summary:
                last_summary.resume = answer_data
                last_summary.save()
            else:
                AnswerSummary.objects.create(bdo_class=bdo_class, resume=answer_data)

    def handle(self, *args, **options):
        begin = time.time()

        print("Running...")

        self.run_command()

        print("\nSuccess! :)")
        print(f"Done with {time.time() - begin}s")
