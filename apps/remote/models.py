from django.db import models


# Create your models here.
class Config(models.Model):

    CONFIG_EMPTY = 0
    CONFIG_SCREEN = 1

    TYPES = [
        (CONFIG_EMPTY, 'empty'),
        (CONFIG_SCREEN, 'scree')
    ]
    type = models.IntegerField(default=CONFIG_EMPTY, choices=TYPES)
    value = models.TextField()


class Screenshot(models.Model):
    image = models.ImageField(upload_to='screenshot/')
