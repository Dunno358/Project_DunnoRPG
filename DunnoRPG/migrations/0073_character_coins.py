# Generated by Django 4.1.7 on 2023-07-11 15:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0072_alter_charitems_durability_alter_charitems_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='coins',
            field=models.IntegerField(default=5),
        ),
    ]
