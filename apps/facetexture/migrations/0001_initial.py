# Generated by Django 3.2.9 on 2022-06-22 01:27

from django.db import migrations, models
import django.db.models.deletion
import facetexture.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Facetexture',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='auth.user')),
                ('characters', models.JSONField(default=facetexture.models.Facetexture.characteres_json_default)),
            ],
        ),
    ]
