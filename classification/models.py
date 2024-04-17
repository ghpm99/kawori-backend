from django.db import models

from facetexture.models import BDOClass
from django.contrib.auth.models import User


# Create your models here.
class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    bdo_class = models.ForeignKey(BDOClass, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    vote = models.IntegerField(max_length=10, default=0)
