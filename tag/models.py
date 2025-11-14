from django.db import models
from django.contrib.auth.models import User

from budget.models import Budget


# Create your models here.
class Tag(models.Model):

    class Meta:
        db_table = "financial_tag"

    name = models.TextField(max_length=255)
    color = models.CharField(max_length=7, null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)


class BudgetTag(models.Model):

    class Meta:
        db_table = "financial_budget_tag"

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
