# Generated by Django 4.2.1 on 2023-08-29 23:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0079_skills_uses_left'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='extra_capacity',
            field=models.IntegerField(default=0),
        ),
    ]