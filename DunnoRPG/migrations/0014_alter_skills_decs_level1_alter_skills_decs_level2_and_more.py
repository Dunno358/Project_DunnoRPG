# Generated by Django 4.1.7 on 2023-03-31 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0013_skills_decs_cost'),
    ]

    operations = [
        migrations.AlterField(
            model_name='skills_decs',
            name='level1',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='skills_decs',
            name='level2',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='skills_decs',
            name='level3',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='skills_decs',
            name='level4',
            field=models.TextField(blank=True, null=True),
        ),
    ]
