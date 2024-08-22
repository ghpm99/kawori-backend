from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Contract(models.Model):
    name = models.TextField(max_length=255)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    value_open = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    value_closed = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    def set_value(self, value):
        self.value = self.value + value
        self.value_open += value
        self.save()

    def close_value(self, value):
        self.value_open -= value
        self.value_closed += value
        self.save()


class Tag(models.Model):
    name = models.TextField(max_length=255)
    color = models.CharField(max_length=7, null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT)


class Invoice(models.Model):

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


class Payment(models.Model):

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


class Month(models.Model):

    MONTH_EMPTY = 0
    MONTH_PROJECTION = 1
    MONTH_CALCULATED = 2
    MONTH_ACCOUNTED = 3

    STATUS = [
        (MONTH_EMPTY, 'empty'),
        (MONTH_PROJECTION, 'projection'),
        (MONTH_CALCULATED, 'calculated'),
        (MONTH_ACCOUNTED, 'accounted')
    ]
    status = models.IntegerField(default=MONTH_EMPTY, choices=STATUS)
    month = models.IntegerField()
    year = models.IntegerField()
    total = models.IntegerField()
