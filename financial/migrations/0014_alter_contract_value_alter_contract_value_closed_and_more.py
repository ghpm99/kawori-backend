# Generated by Django 4.2.15 on 2024-08-22 01:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0013_auto_20221007_0045'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='contract',
            name='value_closed',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='contract',
            name='value_open',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='installments',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='value_closed',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='value_open',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='payment',
            name='fixed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='payment',
            name='installments',
            field=models.IntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='payment',
            name='value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]