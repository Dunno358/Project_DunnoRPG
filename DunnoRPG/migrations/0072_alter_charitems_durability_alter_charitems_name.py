# Generated by Django 4.1.7 on 2023-07-07 14:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0071_eq_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='charitems',
            name='durability',
            field=models.IntegerField(blank=True, default=50, null=True),
        ),
        migrations.AlterField(
            model_name='charitems',
            name='name',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
