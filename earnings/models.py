from django.db import models


# Create your models here.
class Revenue(models.Model):

    class Meta:
        db_table = "financial_revenue"
