from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Facetexture(models.Model):

    def characteres_json_default():
        return {
            'characters': []
        }

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    characters = models.JSONField(default=characteres_json_default)


class BDOClass(models.Model):
    name = models.CharField(max_length=64, unique=True)
    abbreviation = models.CharField(max_length=32, unique=True)
    image = models.ImageField(upload_to='bdoclass/')
    class_image = models.ImageField(upload_to='classimage/', null=True)
    color = models.CharField(max_length=7, null=True)
    class_order = models.IntegerField(default=1)


class PreviewBackground(models.Model):
    image = models.ImageField(upload_to='background/')


class Character(models.Model):
    active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=128)
    show = models.BooleanField()
    bdoClass = models.ForeignKey(BDOClass, on_delete=models.PROTECT)
    image = models.CharField(max_length=128)
    order = models.IntegerField()
    upload = models.BooleanField()
