# Generated by Django 4.2.1 on 2023-07-28 21:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0074_cities'),
    ]

    operations = [
        migrations.AddField(
            model_name='eq',
            name='amount',
            field=models.IntegerField(default=1),
        ),
    ]
