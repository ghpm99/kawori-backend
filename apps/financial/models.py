from django.db import models


# Create your models here.
class Contract(models.Model):
    name = models.TextField(max_length=255)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_open = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_closed = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)


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
    installments = models.IntegerField()
    payment_date = models.DateField(null=True)
    fixed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_open = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_closed = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)


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
    installments = models.IntegerField()
    payment_date = models.DateField()
    fixed = models.BooleanField()
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)


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


class Tag(models.Model):
    name = models.TextField(max_length=255)
