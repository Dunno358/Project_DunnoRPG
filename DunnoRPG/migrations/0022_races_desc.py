# Generated by Django 4.1.7 on 2023-04-06 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0021_alter_races_skills_alter_races_statminus_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='races',
            name='desc',
            field=models.TextField(blank=True),
        ),
    ]
