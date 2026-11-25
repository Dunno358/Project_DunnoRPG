import re

from django.db import transaction
from django.db.models import OuterRef, Subquery

from .. import models


READ_BOOKS_EFFECT = 'Przeczytano książki'


def parse_amount(value):
    value = value.strip()
    if value.endswith("M"):
        return -abs(int(value[:-1]))
    return int(value)


@transaction.atomic
def add_active_effect(owner, character, name, time, desc='', refresh_time=None):
    effects = models.Effects.objects.filter(owner=owner, character=character)
    definitions = models.Effects_Decs.objects.order_by('pk')
    visited = set()
    while name not in visited:
        visited.add(name)
        definition = definitions.filter(name=name).first()
        actions = (definition.actions or '').split(';') if definition else []
        for action in actions:
            change = re.fullmatch(r'change([1-9][0-9]*)-(.+)', action.strip())
            if not change:
                continue
            target = change[2].strip()
            if target in visited or not definitions.filter(name=target).exists():
                continue
            # Serialize applications for a character before inspecting previous copies.
            models.Character.objects.select_for_update().filter(owner=owner, name=character).first()
            count = int(change[1])
            previous = list(effects.filter(name=name).order_by('pk')[:count - 1])
            if len(previous) + 1 < count:
                return models.Effects.objects.create(owner=owner, character=character, name=name, time=time, desc=desc)
            time = (int(time) + sum(effect.time for effect in previous) + count - 1) // count
            effects.filter(pk__in=[effect.pk for effect in previous]).delete()
            name = target
            refresh_time = None
            break
        else:
            if refresh_time is not None:
                existing = effects.filter(name=name).order_by('pk').first()
                if existing:
                    existing.time = refresh_time
                    existing.save(update_fields=['time'])
                    return existing
            return models.Effects.objects.create(owner=owner, character=character, name=name, time=time, desc=desc)


def active_effects(character):
    if isinstance(character, dict):
        name, owner = character['name'], character.get('owner')
    else:
        name, owner = getattr(character, 'name', character), getattr(character, 'owner', None)
    effects = models.Effects.objects.filter(character=name)
    if owner is not None:
        effects = effects.filter(owner=owner)
    definitions = models.Effects_Decs.objects.filter(name=OuterRef('name')).order_by('pk')
    return effects.annotate(
        description=Subquery(definitions.values('desc')[:1]),
        actions=Subquery(definitions.values('actions')[:1]),
    ).order_by('pk')


def effect_actions(effects):
    for effect in effects:
        for index, action in enumerate((effect.actions or '').split(';')):
            yield effect, index, action.strip()


def mobility_penalty(character):
    penalty = 0
    for _, _, action in effect_actions(active_effects(character)):
        match = re.fullmatch(r'mobility-(?:M([0-9]+)|([0-9]+)M)', action, re.IGNORECASE)
        if match:
            penalty += int(match[1] or match[2])
    return penalty


def mobility_percent_modifier(character):
    return -sum(
        int(match[1]) for _, _, action in effect_actions(active_effects(character))
        if (match := re.fullmatch(r'mobility-([0-9]+)pcM', action, re.IGNORECASE))
    )


def mobility_cap(character):
    return min((
        int(match[1]) for _, _, action in effect_actions(active_effects(character))
        if (match := re.fullmatch(r'mobility-max([0-9]+)', action, re.IGNORECASE))
    ), default=None)


def effect_stat_modifier(character, field):
    pattern = rf'{re.escape(field)}([+-][0-9]+)'
    return sum(
        int(match[1]) for _, _, action in effect_actions(active_effects(character))
        if (match := re.fullmatch(pattern, action, re.IGNORECASE))
    )


def adrenaline_percent(character):
    return min(100, sum(
        int(match[1]) for _, _, action in effect_actions(active_effects(character))
        if (match := re.fullmatch(r'adrenaline-([0-9]+)', action, re.IGNORECASE))
    ))


def disadvantage_count(character):
    return sum(action == 'disadvantageAll' for _, _, action in effect_actions(active_effects(character)))


def round_effects(effects):
    rolls = []
    actions_left = []
    hp_changes = []
    mobility_modifier = 0
    for effect, index, action in effect_actions(effects):
        damage = re.fullmatch(r'damageAll(\|ignoreArmor)?-K([1-9][0-9]*)', action)
        action_count = re.fullmatch(r'action-([0-9]+)', action)
        hp_change = re.fullmatch(r'addHP-([+-]?[0-9]+M?)', action)
        mobility = re.fullmatch(r'mobility-([0-9]+)pc', action, re.IGNORECASE)
        mobility_penalty = re.fullmatch(r'mobility\|endRound-([0-9]+)pcM', action, re.IGNORECASE)
        if damage:
            rolls.append({
                'field': f'effect_roll_{effect.pk}_{index}',
                'name': effect.name,
                'sides': int(damage[2]),
                'ignore_armor': bool(damage[1]),
            })
        elif action_count:
            actions_left.append(int(action_count[1]))
        elif hp_change:
            hp_changes.append(parse_amount(hp_change[1]))
        elif mobility:
            mobility_modifier += int(mobility[1])
        elif mobility_penalty:
            mobility_modifier -= int(mobility_penalty[1])
        elif action.lower() == 'mobility-100':
            mobility_modifier += 100
    return rolls, min(actions_left) if actions_left else 1, hp_changes, mobility_modifier
