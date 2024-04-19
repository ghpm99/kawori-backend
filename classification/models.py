from django.contrib.postgres.fields import ArrayField
from django.db import models

from facetexture.models import BDOClass
from django.contrib.auth.models import User


class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    bdo_class = models.ForeignKey(BDOClass, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    vote = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    like_count = models.IntegerField()
    dislike_count = models.IntegerField()


class Path(models.Model):
    url = models.CharField(max_length=200)
    affected_class = ArrayField(models.IntegerField())
    created_at = models.DateTimeField(auto_now_add=True)
