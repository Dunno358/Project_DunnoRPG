from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('DunnoRPG', '0122_items_extra_capacity_items_mobility_items_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='eq',
            name='additional_description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='charitems',
            name='additional_description',
            field=models.TextField(blank=True),
        ),
    ]
