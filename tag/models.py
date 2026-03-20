from django.contrib.auth.models import User
from django.db import models


# Create your models here.
class Tag(models.Model):

    class Meta:
        db_table = "financial_tag"
        unique_together = ("user", "name")

    name = models.TextField(max_length=255)
    color = models.CharField(max_length=7, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
