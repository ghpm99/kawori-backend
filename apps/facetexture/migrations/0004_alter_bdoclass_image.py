# Generated by Django 3.2.9 on 2022-07-03 23:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facetexture', '0003_bdoclass_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bdoclass',
            name='image',
            field=models.ImageField(upload_to='bdoclass/'),
        ),
    ]
