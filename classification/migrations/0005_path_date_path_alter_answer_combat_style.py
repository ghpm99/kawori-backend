# Generated by Django 4.2.7 on 2024-06-23 23:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classification', '0004_answer_combat_style'),
    ]

    operations = [
        migrations.AddField(
            model_name='path',
            name='date_path',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='answer',
            name='combat_style',
            field=models.IntegerField(choices=[(1, 'Despertar'), (2, 'Sucessão')], default=1, null=True),
        ),
    ]