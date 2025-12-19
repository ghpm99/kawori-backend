from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User

from contract.models import Contract
from tag.models import Tag


# Create your models here.
class Invoice(models.Model):

    class Meta:
        db_table = "financial_invoice"

    class Type(models.IntegerChoices):
        CREDIT = 0, "credit"
        DEBIT = 1, "debit"

    STATUS_OPEN = 0
    STATUS_DONE = 1

    STATUS = [(STATUS_OPEN, "open"), (STATUS_DONE, "done")]
    status = models.IntegerField(default=STATUS_OPEN, choices=STATUS)
    type = models.IntegerField(default=Type.DEBIT, choices=Type.choices)
    name = models.TextField(max_length=255)
    date = models.DateField()
    installments = models.IntegerField(default=1)
    payment_date = models.DateField(null=True)
    fixed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0.0))
    value_open = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0.0))
    value_closed = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0.0))
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name="invoices", blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def set_value(self, value):
        self.value += value
        self.value_open += value
        self.save()

    def get_next_open_payment_date(self):
        return (
            self.payment_set.filter(status=self.STATUS_OPEN, active=True)
            .order_by("payment_date")
            .values_list("payment_date", flat=True)
            .first()
        )

    def close_value(self, value):
        self.value_open -= value
        self.value_closed += value

        if self.value_open == 0:
            self.status = self.STATUS_DONE

        next_payment_date = self.get_next_open_payment_date()
        if next_payment_date:
            self.payment_date = next_payment_date

        self.save()
