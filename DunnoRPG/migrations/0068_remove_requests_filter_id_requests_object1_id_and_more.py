# Generated by Django 4.1.7 on 2023-07-01 14:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0067_remove_requests_character_requests_char_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='requests',
            name='filter_id',
        ),
        migrations.AddField(
            model_name='requests',
            name='object1_id',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='requests',
            name='object2_id',
            field=models.IntegerField(default=0),
        ),
    ]
