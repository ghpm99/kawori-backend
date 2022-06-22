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
