from django.db import models
from django.contrib.auth.models import User
from invoice.models import Invoice


# Create your models here.
class Payment(models.Model):

    class Meta:
        db_table = 'financial_payment'

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
    payment_date = models.DateField()
    fixed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    def set_value(self, value):
        self.invoice.set_value(value)
        self.value = value
        self.save()

    def close_value(self):
        self.invoice.close_value(self.value)
        self.status = self.STATUS_DONE
        self.save()
