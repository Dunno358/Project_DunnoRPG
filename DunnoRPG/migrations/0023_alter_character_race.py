# Generated by Django 4.1.7 on 2023-04-06 18:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0022_races_desc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='character',
            name='race',
            field=models.CharField(max_length=30),
        ),
    ]
