# Generated by Django 4.1.7 on 2023-06-17 15:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0059_rename_item_name_charitems_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='character',
            name='LeftHand',
        ),
        migrations.RemoveField(
            model_name='character',
            name='RightHand',
        ),
    ]
