from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0124_items_hiddenskill'),
    ]

    operations = [
        migrations.AddField(
            model_name='items',
            name='unobtainable',
            field=models.BooleanField(default=False),
        ),
    ]
