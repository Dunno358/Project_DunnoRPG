# Generated by Django 4.1.7 on 2023-04-04 14:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0016_skills_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='items',
            name='type',
            field=models.CharField(max_length=50, null=True),
        ),
    ]
