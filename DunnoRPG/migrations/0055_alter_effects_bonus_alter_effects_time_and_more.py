# Generated by Django 4.1.7 on 2023-05-08 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0054_effects_bonus_effects_decs_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='effects',
            name='bonus',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='effects',
            name='time',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='effects_decs',
            name='bonus',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='effects_decs',
            name='time',
            field=models.IntegerField(default=0),
        ),
    ]
