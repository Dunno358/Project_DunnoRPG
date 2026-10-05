from django.db import migrations, models


def initialize_use_amount(apps, schema_editor):
    Item = apps.get_model('DunnoRPG', 'Items')
    Eq = apps.get_model('DunnoRPG', 'Eq')
    CharItems = apps.get_model('DunnoRPG', 'CharItems')
    database = schema_editor.connection.alias
    for name, use_amount in Item.objects.using(database).exclude(use_amount=None).values_list('name', 'use_amount'):
        Eq.objects.using(database).filter(name=name).update(use_amount=use_amount)
        CharItems.objects.using(database).filter(name=name).update(use_amount=use_amount)


class Migration(migrations.Migration):
    dependencies = [('DunnoRPG', '0134_cities_healer_cities_repair')]

    operations = [
        migrations.AddField(
            model_name='charitems',
            name='use_amount',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eq',
            name='use_amount',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(initialize_use_amount, migrations.RunPython.noop),
    ]
