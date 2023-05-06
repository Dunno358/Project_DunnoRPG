from django import template
from DunnoRPG import models

register = template.Library()

@register.filter
def getItemStatByName(itemName):
    try:
        item = models.Items.objects.all().filter(name=itemName).values()[0]
        if item['type'].lower() != 'shield':
            bonus = item['diceBonus']
            if bonus >= 0:
                return f"1K+{item['diceBonus']}, {item['AP']}AP"
            else:
                return f"1K{item['diceBonus']}, {item['AP']}AP"
        else:
            return item['block']
    except:
        pass
    
@register.filter
def getItemAP(itemName):
    return models.Items.objects.all().filter(name=itemName).values()[0]['AP']

@register.filter
def getItemBonus(itemName):
    return models.Items.objects.all().filter(name=itemName).values()[0]['diceBonus']

@register.filter
def getItemBlock(itemName):
    return models.Items.objects.all().filter(name=itemName).values()[0]['block']
    
@register.filter
def isDualHanded(itemName):
    try:
        return models.Items.objects.all().filter(name=itemName).values()[0]['dualHanded']
    except:
        pass    

@register.filter
def isShield(itemName):
    if models.Items.objects.all().filter(name=itemName).values()[0]['type'] == 'shield':
        return True
    else:
        return False

@register.filter
def isNotEmpty(hand):
    if len(hand)>0:
        return True
    else:
        return False
    
@register.filter
def isPreffereOrUnliked(character, itemName):
    if len(itemName)>0:
        try:
            weapon_type = models.Items.objects.all().filter(name=itemName).values()[0]['type'].lower()
            character_bonus = models.Character.objects.all().filter(name=character).values()[0]['weaponBonus']
            charater_preffered = models.Character.objects.all().filter(name=character).values()[0]['preferredWeapons'].split(';')
            character_unliked = models.Character.objects.all().filter(name=character).values()[0]['unlikedWeapons'].split(';')
            
            if weapon_type in charater_preffered:
                return f"+{character_bonus}"
            elif weapon_type in character_unliked:
                return -int(character_bonus)
            else:
                return "+0"
        except:
            return "+0"
    else:
        return "Empty"

@register.filter
def getMod(character,stat_for_mod):
    value = 0
    for stat in models.Mods.objects.all().filter(character=character['name'], field=stat_for_mod).values():
        value += stat['value']
    if value>=0:
        value = f"+{value}"
    return value

@register.filter
def getCharacterEffects(character):
    return models.Effects.objects.all().filter(character=character['name']).values()