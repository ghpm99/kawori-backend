# Generated by Django 4.2 on 2023-06-28 01:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facetexture', '0007_character'),
    ]

    operations = [
        migrations.AlterField(
            model_name='character',
            name='image',
            field=models.CharField(max_length=128),
        ),
        migrations.AlterField(
            model_name='character',
            name='name',
            field=models.CharField(max_length=128),
        ),
    ]