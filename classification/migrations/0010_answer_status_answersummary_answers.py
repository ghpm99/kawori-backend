# Generated by Django 4.2.7 on 2024-06-29 02:08

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classification', '0009_remove_answersummary_question'),
    ]

    operations = [
        migrations.AddField(
            model_name='answer',
            name='status',
            field=models.IntegerField(choices=[(1, 'Aguardando'), (2, 'Processando'), (3, 'Processado')], default=1),
        ),
        migrations.AddField(
            model_name='answersummary',
            name='answers',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=[], size=None),
        ),
    ]