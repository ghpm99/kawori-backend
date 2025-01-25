from django.db import models


# Create your models here.
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
