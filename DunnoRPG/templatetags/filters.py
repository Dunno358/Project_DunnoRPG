from django import template
from DunnoRPG import models
from django.apps import apps
from django.shortcuts import get_object_or_404

register = template.Library()

#OBJECT-GET
@register.filter
def getObjectName(model, object_id):
    for listed_model in apps.get_models():
        if listed_model.__name__ == model:
            try:
                return listed_model.objects.filter(id=object_id).first().name
            except:
                return listed_model.objects.filter(id=object_id).first()
    return None

#ITEM-GET
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
def getItemAP(itemName, charId=0):
    print(charId)
    item = get_object_or_404(models.Items, name=itemName)
    if charId != 0:
        char = get_object_or_404(models.Character, id=charId)
        if item.dualHanded and char.chosen_class.lower()=='barbarzyńca: droga rosomaka':
            return item.AP//2
    return item.AP

@register.filter
def getItemArmor(itemName):
    return get_object_or_404(models.Items, name=itemName).armor

@register.filter
def getItemWeight(itemName):
    return get_object_or_404(models.Items, name=itemName).weight

@register.filter
def getItemBonus(itemName):
    bonus = get_object_or_404(models.Items, name=itemName).diceBonus
    if bonus>=0:
        return f"+{bonus}"
    else:
        return bonus

@register.filter
def getItemBlock(itemName):
    return get_object_or_404(models.Items, name=itemName).block

@register.filter
def getMaxDurability(itemName):
   return get_object_or_404(models.Items, name=itemName).maxDurability 

@register.filter
def getItemType(itemName):
    return get_object_or_404(models.Items, name=itemName).type

@register.filter
def getItemRarity(itemName):
    try:
        return models.Items.objects.filter(name=itemName).get().rarity
    except:
        return None
    
@register.filter
def getItemPrice(itemName, full=False):
    try:
        price = models.Items.objects.filter(name=itemName).get().price
        if full:
            return price*2
        else: return price
    except:
        return None
    
@register.filter
def getSkill(itemName):
    try:
        return models.Items.objects.filter(name=itemName).get().skill
    except:
        return False

@register.filter
def getDescId(itemName):
    try:
        return models.Items.objects.filter(name=itemName).values()[0]['id']
    except:
        return ''
   


   
#ITEM-IS
@register.filter
def isDualHanded(itemName):
    try:
        return models.Items.objects.all().filter(name=itemName).values()[0]['dualHanded']
    except:
        pass    

@register.filter
def isShield(itemName):
    try:
        if models.Items.objects.all().filter(name=itemName).values()[0]['type'].lower() == 'shield':
            return True
        else:
            return False
    except:
        return False
    
@register.filter
def isArmor(itemName):
    try:
        if models.Items.objects.all().filter(name=itemName).values()[0]['type'].lower() in ['helmet','armor','torso','boots','gloves','amulet']:
            return True
        else:
            return False
    except:
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




#CHARACTER-GET
@register.filter
def getMod(character,stat_for_mod):
    value = 0
    for stat in models.Mods.objects.all().filter(character=character['name'], field=stat_for_mod).values():
        value += stat['value']
    items = []
    for item in models.CharItems.objects.all().filter(character=character['name']):
        try:
            stats = models.Items.objects.all().filter(name=item.name).first().skillStats.split(';')
            for stat in stats:
                if stat[:-2].lower() == stat_for_mod.lower():
                    if stat[-2] == "+":
                        value += int(stat[-1])
                    elif stat[-2] == "-":
                        value -= int(stat[-1])
        except:
            pass
    if value>=0:
        value = f"+{value}"
    return value

@register.filter
def getCharacterEffects(character):
    return models.Effects.objects.all().filter(character=character['name']).values()

@register.filter
def getCharacterEffectsCount(character):
    return len(models.Effects.objects.all().filter(character=character['name']).values())

@register.filter
def getEffectDesc(effect):
    return models.Effects_Decs.objects.all().filter(name=effect).values()[0]['desc']

@register.filter
def getEffectsBonus(character_name, action):
    if action=='accuraccy':
        categories = ['cel','all']
    elif action=='attack':
        categories = ['all','attack','attack&parry']
    elif action=='parry':
        categories = ['all','parry','attack&parry']
    elif action=='dodge':
        categories = ['all','dodge']
    
    
    acc_effects = []
    bonus = 0

    for effect in models.Effects_Decs.objects.all().values():
        if effect['category'] in categories:
            acc_effects.append(effect['name'])
    
    for effect in models.Effects.objects.all().filter(character=character_name).values():
        if effect['name'] in acc_effects:
            bonus += effect['bonus']

    return bonus

@register.filter
def getAmuletAttackBonus(charName):
    try:
        amulet = models.Items.objects.filter(
            name=models.CharItems.objects.filter(character=charName, position='Amulet').first().name
            ).first()
        return amulet.diceBonus
    except:
        return 0

@register.filter
def getArmor(charName):
    char = get_object_or_404(models.Character, name=charName)
    helmet = models.CharItems.objects.filter(character=charName, position='Helmet').first()
    torso = models.CharItems.objects.filter(character=charName, position='Torso').first()
    boots = models.CharItems.objects.filter(character=charName, position='Boots').first()
    gloves = models.CharItems.objects.filter(character=charName, position='Gloves').first()
    amulets = models.CharItems.objects.filter(character=charName, position='Amulet').first()
    items = [helmet,torso,boots,gloves,amulets]
    
    armor = 0
    
    for item in items:
        try:
            armor += models.Items.objects.filter(name=item.name).first().armor
        except:
            pass
    
    return armor

@register.filter
def getArmorWeight(charName):
    helmet = models.CharItems.objects.filter(character=charName, position='Helmet').first()
    torso = models.CharItems.objects.filter(character=charName, position='Torso').first()
    boots = models.CharItems.objects.filter(character=charName, position='Boots').first()
    gloves = models.CharItems.objects.filter(character=charName, position='Gloves').first()
    amulets = models.CharItems.objects.filter(character=charName, position='Amulet').first()
    items = [helmet,torso,boots,gloves,amulets]  
    
    weight = 0
    
    for item in items:
        try:
            weight += models.Items.objects.filter(name=item.name).first().weight
        except:
            pass
        
    return weight 

@register.filter
def getStatFromItems(charName,statToGet):
    items = models.CharItems.objects.filter(character=charName)
    mod = 0

    for item in items:
        item_details = models.Items.objects.filter(name=item.name).first()
        if item_details.skillStats != None:
            stats = item_details.skillStats.split(';')
            for stat in stats:
                if stat[:-2]==statToGet:
                    mod += int(stat[-2:])

    return mod

@register.filter
def getCharacterName(char_id):
    character = models.Character.objects.filter(id=char_id).first()
    try:
        return character.name
    except:
        return "No character"
    
#CHARACTER-IS
@register.filter
def isNotEmpty(hand):
    if len(hand)>0:
        return True
    else:
        return False