from django.db import models
from django.contrib.auth.models import User

from contract.models import Contract
from tag.models import Tag


# Create your models here.
class Invoice(models.Model):

    class Meta:
        db_table = 'financial_invoice'

    TYPE_CREDIT = 0
    TYPE_DEBIT = 1

    TYPES = [
        (TYPE_CREDIT, 'credit'),
        (TYPE_DEBIT, 'debit')
    ]

    STATUS_OPEN = 0
    STATUS_DONE = 1

    STATUS = [
        (STATUS_OPEN, 'open'),
        (STATUS_DONE, 'done')
    ]
    status = models.IntegerField(default=STATUS_OPEN, choices=STATUS)
    type = models.IntegerField(default=TYPE_CREDIT, choices=TYPES)
    name = models.TextField(max_length=255)
    date = models.DateField()
    installments = models.IntegerField(default=1)
    payment_date = models.DateField(null=True)
    fixed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    value_open = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    value_closed = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    def set_value(self, value):
        self.contract.set_value(value)
        self.value += value
        self.value_open += value
        self.save()

    def close_value(self, value):
        self.contract.close_value(value)
        self.value_open -= value
        self.value_closed += value

        if self.value_open == 0:
            self.status = self.STATUS_DONE
        self.save()
