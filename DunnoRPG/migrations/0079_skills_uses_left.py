# Generated by Django 4.1.7 on 2023-08-13 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0078_skills_decs_useslvl1_skills_decs_useslvl2_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='skills',
            name='uses_left',
            field=models.IntegerField(default=1),
        ),
    ]
