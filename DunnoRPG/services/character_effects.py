import re

from django.db.models import OuterRef, Subquery

from .. import models
from .item_effects import parse_amount


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


def disadvantage_count(character):
    return sum(action == 'disadvantageAll' for _, _, action in effect_actions(active_effects(character)))


def round_effects(effects):
    rolls = []
    actions_left = []
    hp_changes = []
    for effect, index, action in effect_actions(effects):
        damage = re.fullmatch(r'damageAll(\|ignoreArmor)?-K([1-9][0-9]*)', action)
        action_count = re.fullmatch(r'action-([0-9]+)', action)
        hp_change = re.fullmatch(r'addHP-([+-]?[0-9]+M?)', action)
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
    return rolls, min(actions_left) if actions_left else 1, hp_changes
