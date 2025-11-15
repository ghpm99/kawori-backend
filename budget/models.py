from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from tag.models import Tag


class Budget(models.Model):

    class Meta:
        db_table = "financial_budget"

    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentual do orçamento (0.00 - 100.00)",
        default=Decimal("0.00"),
    )
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, related_name="budget")
