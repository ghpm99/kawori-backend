from django.contrib.postgres.fields import ArrayField
from django.db import models

from facetexture.models import BDOClass
from django.contrib.auth.models import User


class Question(models.Model):
    question_text = models.CharField(max_length=200)
    text = models.CharField(max_length=200, default='')
    question_details = models.TextField(default='')
    pub_date = models.DateTimeField('date published')


class Answer(models.Model):
    AWAKENING = 1
    SUCCESSION = 2

    COMBAT_STYLES = [
        (AWAKENING, 'Despertar'),
        (SUCCESSION, 'Sucessão')
    ]

    STATUS_OPEN = 1
    STATUS_PROCESSING = 2
    STATUS_DONE = 3

    STATUS = [
        (STATUS_OPEN, 'Aguardando'),
        (STATUS_PROCESSING, 'Processando'),
        (STATUS_DONE, 'Processado'),
    ]

    status = models.IntegerField(default=STATUS_OPEN, choices=STATUS)
    bdo_class = models.ForeignKey(BDOClass, on_delete=models.CASCADE)
    combat_style = models.IntegerField(default=AWAKENING, choices=COMBAT_STYLES, null=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    vote = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    like_count = models.IntegerField(default=0)
    dislike_count = models.IntegerField(default=0)
    height = models.FloatField(default=1)


class AnswerSummary(models.Model):
    AWAKENING = 1
    SUCCESSION = 2

    COMBAT_STYLES = [
        (AWAKENING, 'Despertar'),
        (SUCCESSION, 'Sucessão')
    ]

    bdo_class = models.ForeignKey(BDOClass, on_delete=models.CASCADE)
    updated_at = models.DateField(auto_now=True)
    resume = models.JSONField(default=dict)


class Path(models.Model):
    url = models.CharField(max_length=200)
    affected_class = ArrayField(models.IntegerField())
    date_path = models.DateField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
