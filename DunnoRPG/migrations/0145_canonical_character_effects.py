from django.db import migrations


LEGACY_EFFECTS = {
    'Utrudnienie (upojenie, reakcja)': ('Utrudnienie', 'Jesteś pijany'),
    'Nierówny krok (upojenie)': ('Pijany', 'Jesteś pijany'),
    'Utrudnienie (kac, akcja)': ('Utrudnienie', 'Masz kaca'),
    'Utrudnienie (kac, reakcja)': ('Utrudnienie', 'Masz kaca'),
    'Nierówny krok (kac)': ('Kac', 'Masz kaca'),
    'Utrudnienie (głód)': ('Utrudnienie', 'Odczuwasz Głód'),
    'Utrudnienie (pragnienie)': ('Utrudnienie', 'Odczuwasz Pragnienie'),
}


def canonicalize_effects(apps, schema_editor):
    alias = schema_editor.connection.alias
    definitions = apps.get_model('DunnoRPG', 'Effects_Decs').objects.using(alias)
    effects = apps.get_model('DunnoRPG', 'Effects').objects.using(alias)
    characters = apps.get_model('DunnoRPG', 'Character').objects.using(alias)
    skills = apps.get_model('DunnoRPG', 'Skills').objects.using(alias)

    definitions.filter(name__in=LEGACY_EFFECTS).delete()
    for pk, name, category, desc, actions in (
        (1, 'Utrudnienie', 'Utrudnienie', 'Dodatkowe K6 odejmowane od wyniku.', 'disadvantageAll'),
        (2, 'Nierówny krok', 'Mobility', 'Mobilność -1.', 'Mobility-M1'),
        (10, 'Podpity', 'Alkohol', 'Siła +1, Charyzma +1, Celność -2', 'SIŁ+1;CHAR+1;CEL-2'),
        (11, 'Pijany', 'Alkohol', 'Siła +2, Celność -4, Mobilność -1.', 'SIŁ+2;CEL-4;Mobility-M1'),
        (12, 'Kac', 'Alkohol', 'Mobilność -1.', 'Mobility-M1'),
    ):
        definition = definitions.filter(name=name).order_by('pk').first()
        if definition is None:
            available_id = {'pk': pk} if not definitions.filter(pk=pk).exists() else {}
            definitions.create(name=name, category=category, desc=desc, actions=actions, **available_id)
        elif not definition.actions:
            definition.actions = actions
            definition.save(update_fields=['actions'])

    for effect in list(effects.filter(name__in=LEGACY_EFFECTS)):
        name, reason = LEGACY_EFFECTS[effect.name]
        desc = effect.desc or reason
        existing = effects.filter(owner=effect.owner, character=effect.character, name=name, desc=desc).first()
        if existing:
            if existing.time < effect.time:
                existing.time = effect.time
                existing.save(update_fields=['time'])
            effect.delete()
        else:
            effect.name = name
            effect.desc = desc
            effect.save(update_fields=['name', 'desc'])

    for character in characters.exclude(alcohol='0').iterator():
        try:
            alcohol = int(character.alcohol)
        except (TypeError, ValueError):
            continue
        if alcohol <= 0:
            continue
        strong_head = skills.filter(
            owner=character.owner, character=character.name, skill__iexact='Mocna głowa',
        ).first()
        limit = 3 + (strong_head.level if strong_head else 0)
        if alcohol > limit:
            names, desc = ('Pijany', 'Utrudnienie'), 'Jesteś pijany'
        else:
            names, desc = ('Podpity',), 'Odczuwasz upojenie alkoholem'
        for name in names:
            effects.get_or_create(
                owner=character.owner, character=character.name, name=name, desc=desc,
                defaults={'time': 1000},
            )


class Migration(migrations.Migration):
    dependencies = [('DunnoRPG', '0144_simplify_effect_fields')]

    operations = [migrations.RunPython(canonicalize_effects, migrations.RunPython.noop)]
