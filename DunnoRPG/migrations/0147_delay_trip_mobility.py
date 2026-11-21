import re

from django.db import migrations, models


def update_trip_actions(apps, schema_editor, pattern, old, new):
    definitions = apps.get_model('DunnoRPG', 'Effects_Decs').objects.using(schema_editor.connection.alias)
    for effect in definitions.filter(name='Potknięcie'):
        actions = [
            re.sub(old, new, action, count=1, flags=re.IGNORECASE)
            if re.fullmatch(pattern, action.strip(), re.IGNORECASE) else action
            for action in effect.actions.split(';')
        ]
        effect.actions = ';'.join(actions)
        effect.save(update_fields=['actions'])


def delay_trip(apps, schema_editor):
    update_trip_actions(apps, schema_editor, r'mobility-[0-9]+pcM', r'-', '|endRound-')


def restore_immediate_trip(apps, schema_editor):
    update_trip_actions(apps, schema_editor, r'mobility\|endRound-[0-9]+pcM', r'\|endRound-', '-')
    characters = apps.get_model('DunnoRPG', 'Character').objects.using(schema_editor.connection.alias)
    characters.filter(round_mobility_bonus__lt=0).update(round_mobility_bonus=0)


class Migration(migrations.Migration):
    dependencies = [('DunnoRPG', '0146_round_effect_state')]

    operations = [
        migrations.AlterField(
            model_name='character',
            name='round_mobility_bonus',
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(delay_trip, restore_immediate_trip),
    ]
