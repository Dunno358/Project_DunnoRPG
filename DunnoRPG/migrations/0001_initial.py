# Generated by Django 4.1.7 on 2023-03-20 15:48

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NPC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Health_Points', models.CharField(max_length=255)),
                ('Armor_Points', models.CharField(max_length=255)),
            ],
        ),
    ]