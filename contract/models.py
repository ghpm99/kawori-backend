from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Contract(models.Model):

    class Meta:
        db_table = 'financial_contract'

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
