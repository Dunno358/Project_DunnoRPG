# Generated by Django 4.1.7 on 2023-04-15 20:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0029_effects'),
    ]

    operations = [
        migrations.AddField(
            model_name='effects',
            name='category',
            field=models.CharField(max_length=150, null=True),
        ),
    ]