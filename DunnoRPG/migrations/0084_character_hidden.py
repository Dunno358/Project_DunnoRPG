# Generated by Django 4.2.1 on 2023-10-09 22:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0083_alter_character_model_url_alter_character_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='hidden',
            field=models.BooleanField(default=False),
        ),
    ]
