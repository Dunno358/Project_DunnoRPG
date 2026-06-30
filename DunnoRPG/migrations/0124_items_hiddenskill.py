from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0123_eq_charitems_additional_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='items',
            name='hiddenSkill',
            field=models.TextField(blank=True),
        ),
    ]
