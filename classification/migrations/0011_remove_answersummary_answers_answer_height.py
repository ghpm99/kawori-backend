# Generated by Django 4.2.7 on 2024-06-29 02:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classification', '0010_answer_status_answersummary_answers'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='answersummary',
            name='answers',
        ),
        migrations.AddField(
            model_name='answer',
            name='height',
            field=models.FloatField(default=1),
        ),
    ]