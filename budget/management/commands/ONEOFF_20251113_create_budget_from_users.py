import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Lower, Trim

from invoice.models import Invoice
from tag.models import Tag


class Command(BaseCommand):
    """
    Register colors in Bdo Class
    """

    def remove_duplicate_tags(self):
        duplicates = (
            Tag.objects.annotate(normalized_name=Lower(Trim("name")))
            .values("normalized_name", "user")
            .annotate(count_id=Count("id"))
            .filter(count_id__gt=1)
        )

        for duplicate in duplicates:
            tags = (
                Tag.objects.annotate(normalized_name=Lower(Trim("name")))
                .filter(
                    normalized_name=duplicate["normalized_name"],
                    user_id=duplicate["user"],
                )
                .order_by("id")
            )

            tags_to_delete = tags[1:]
            tag_to_keep = tags[0]
            for tag in tags_to_delete:
                invoices = Invoice.objects.filter(tags=tag)

                for invoice in invoices:
                    invoice.tags.add(tag_to_keep)
                    invoice.tags.remove(tag)

                if hasattr(tag, "budget"):
                    budget = tag.budget
                    budget.tag = tag_to_keep
                    budget.save()

                tag.delete()

    def run_command(self):
        self.remove_duplicate_tags()

        users_with_tags = Tag.objects.values_list("user_id", flat=True).distinct()

        from budget.services import create_default_budgets_for_user

        for user_id in users_with_tags:
            user = User.objects.filter(id=user_id).first()
            if user:
                create_default_budgets_for_user(user)

    def handle(self, *args, **options):
        begin = time.time()

        self.stdout.write(self.style.SUCCESS("Running..."))

        self.run_command()

        self.stdout.write(self.style.SUCCESS("Success! :)"))
        self.stdout.write(self.style.SUCCESS(f"Done with {time.time() - begin}s"))
