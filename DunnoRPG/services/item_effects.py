from dataclasses import dataclass

from django.shortcuts import get_object_or_404

from DunnoRPG import models


@dataclass
class ItemEffectMessage:
    level: str
    text: str


EMPTY_BOTTLE_ACTIONS = {"addHP_Potion", "addWater_Bottle"}


def apply_item_use_effects(char, actions, cost, manage_food_and_water):
    messages = []

    for single_action in actions:
        action_name, amount_value = single_action.split("-", 1)
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
