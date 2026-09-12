from dataclasses import dataclass

from django.shortcuts import get_object_or_404

from DunnoRPG import models


@dataclass
class ItemEffectMessage:
    level: str
    text: str


EMPTY_BOTTLE_ACTIONS = {"addHP_Potion", "addWater_Bottle"}
VALID_STAT_MOD_FIELDS = {"INT", "SIŁ", "ZRE", "CHAR", "CEL", "SPO"}


def apply_item_use_effects(char, actions, cost, manage_food_and_water, sync_alcohol_mods=None, add_consumed_container=True):
    messages = []

    for single_action in actions:
        if single_action == "heal-bandage":
            used_amount, removed_bleeding_count = heal_with_bandage(char)
            bleeding_message = ", usunieto Krwawienie" if removed_bleeding_count else ""
            messages.append(ItemEffectMessage(
                "success",
                f"Uleczono {used_amount} PŻ, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
            messages[-1].text = messages[-1].text.replace(", wykorzystano", f"{bleeding_message}, wykorzystano")
            continue

        action_name, amount_value = single_action.split("-", 1)

        if action_name.startswith("increaseStat:"):
            stat_name = action_name.split(":", 1)[1].strip()
            mod = increase_stat(char, stat_name, amount_value)
            if mod is None:
                messages.append(ItemEffectMessage(
                    "error",
                    f"Nieprawidłowy modyfikator statystyki: {single_action}",
                ))
                continue

            messages.append(ItemEffectMessage(
                "success",
                f"Dodano {mod.value:+d} {mod.field} na {mod.time} rund, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
            continue

        if action_name == "increaseMobility":
            mod = increase_mobility(char, amount_value)
            if mod is None:
                messages.append(ItemEffectMessage(
                    "error",
                    f"Nieprawidłowy modyfikator mobilności: {single_action}",
                ))
                continue

            messages.append(ItemEffectMessage(
                "success",
                f"Dodano {mod.value:+d} mobilności na {mod.time} rund, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
            continue

        amount = int(amount_value)

        if action_name.startswith("addHP"):
            used_amount = add_hp(char, amount)
            messages.append(ItemEffectMessage(
                "success",
                f"Uleczono {used_amount} PŻ, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
        elif action_name.startswith("addFood"):
            char, _ = manage_food_and_water(char, amount, "food")
            messages.append(ItemEffectMessage(
                "success",
                f"Dodano {amount} nasycenia, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
        elif action_name.startswith("addWater"):
            char, _ = manage_food_and_water(char, amount, "water")
            messages.append(ItemEffectMessage(
                "success",
                f"Dodano {amount} napojenia, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
        elif action_name.startswith("addAlcohol"):
            previous_alcohol_level = add_alcohol(char, amount)
            if sync_alcohol_mods is not None:
                sync_alcohol_mods(char, previous_alcohol_level)
            messages.append(ItemEffectMessage(
                "success",
                f"Dodano {amount} alkoholu, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))
        elif action_name.startswith("addEffect:"):
            effect_name = action_name.split(":", 1)[1].strip()
            effect = add_effect(char, effect_name, amount)
            if effect is None:
                messages.append(ItemEffectMessage(
                    "error",
                    f"Nie znaleziono efektu: {effect_name}",
                ))
                continue

            messages.append(ItemEffectMessage(
                "success",
                f"Dodano efekt {effect.name} na {amount} rund, wykorzystano {cost}/{char.actionLeft-cost} akcji",
            ))

    if add_consumed_container:
        add_empty_bottle_if_needed(char, actions)

    return char, messages


def add_hp(char, amount):
    char.HP += amount
    used_amount = amount

    if char.HP > char.fullHP:
        used_amount = int(char.fullHP - int(char.HP - amount))
        char.HP = char.fullHP

    char.exp += 1
    return used_amount


def heal_with_bandage(char):
    heal_amount = 2 if char.inFight else 3
    used_amount = add_hp(char, heal_amount)
    removed_bleeding_count, _ = models.Effects.objects.filter(character=char.name, name="Krwawienie").delete()
    return used_amount, removed_bleeding_count


def add_alcohol(char, amount):
    try:
        alcohol_level = int(char.alcohol)
    except (TypeError, ValueError):
        alcohol_level = 0

    char.alcohol = max(0, alcohol_level + amount)
    return alcohol_level


def add_effect(char, effect_name, time):
    effect_desc = models.Effects_Decs.objects.filter(name=effect_name).first()
    if effect_desc is None:
        return None

    effect, _ = models.Effects.objects.update_or_create(
        owner=char.owner,
        character=char.name,
        name=effect_desc.name,
        defaults={
            "desc": effect_desc.desc,
            "time": time,
            "category": effect_desc.category,
            "source": "item_use",
        },
    )
    return effect


def increase_stat(char, stat_name, payload):
    stat_name = stat_name.upper()
    if stat_name not in VALID_STAT_MOD_FIELDS:
        return None

    return increase_mod(char, stat_name, payload, f"item_use:increaseStat:{stat_name}")


def increase_mobility(char, payload):
    return increase_mod(char, "mobility", payload, "item_use:increaseMobility")


def increase_mod(char, field, payload, source):
    if "|" not in payload:
        return None

    try:
        value_text, time_text = payload.split("|", 1)
        value = int(value_text)
        time = int(time_text)
    except ValueError:
        return None

    if time <= 0:
        return None

    mod, _ = models.Mods.objects.update_or_create(
        owner=char.owner,
        character=char.name,
        field=field,
        source=source,
        defaults={
            "value": value,
            "time": time,
        },
    )
    return mod


def add_empty_bottle_if_needed(char, actions):
    if not any(single_action.split("-", 1)[0] in EMPTY_BOTTLE_ACTIONS for single_action in actions):
        return

    empty_bottle = get_object_or_404(models.Items, name="Pusta buteleczka")
    bottle = models.Eq.objects.filter(character=char.name, name=empty_bottle.name).first()

    if bottle is None:
        models.Eq.objects.create(
            owner=char.owner,
            character=char.name,
            name=empty_bottle.name,
            type=empty_bottle.type,
            weight=empty_bottle.weight,
            durability=empty_bottle.maxDurability,
            amount=1,
        )
        return

    bottle.amount += 1
    bottle.weight = empty_bottle.weight * bottle.amount
    bottle.save()
