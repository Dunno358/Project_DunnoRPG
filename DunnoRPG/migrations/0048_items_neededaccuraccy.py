# Generated by Django 4.1.7 on 2023-05-04 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0047_items_armor'),
    ]

    operations = [
        migrations.AddField(
            model_name='items',
            name='neededAccuraccy',
            field=models.IntegerField(default=50),
        ),
    ]
