# Generated by Django 3.2.9 on 2022-07-04 02:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facetexture', '0004_alter_bdoclass_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='PreviewBackground',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='background/')),
            ],
        ),
    ]
