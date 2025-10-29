from django import template
from DunnoRPG import models
from django.apps import apps
from django.shortcuts import get_object_or_404
import math

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
def getItemArmor(itemName, charId=0):
    char_name = ''
    if charId != 0:
        char = get_object_or_404(models.Character, id=charId)
        char_name = char.name
    normal_armor = get_object_or_404(models.Items, name=itemName).armor

    if char_name=='':
        item = models.CharItems.objects.filter(name=itemName).first()
    else:
        item = models.CharItems.objects.filter(name=itemName, character=char_name).first()

    try:
        armor_from_durability = math.ceil(item.durability / 50)
    except:
        armor_from_durability = normal_armor
    
    if normal_armor != 0:
        return armor_from_durability
    else:
        return normal_armor
    #return get_object_or_404(models.Items, name=itemName).armor - OLD

@register.filter
def getItemWeight(itemName):
    return get_object_or_404(models.Items, name=itemName).weight

@register.filter
def getArmorWeightType(itemName):
    types = { #first index for light armor, second for medium and above is heavy armor
    "Helmet": [1.5, 2.5],
    "Torso": [4,7],
    "Boots": [0.5, 1.1],
    "Gloves": [1, 2],
    "Amulet": [1, 2]
    }

    weightType = ""
    item = get_object_or_404(models.Items, name=itemName)
    weight = item.weight
    type = item.type

    if weight < types[type][0]:
        weightType = "Lekkie"
    elif weight < types[type][1]:
        weightType = "Średnie"
    else:
        weightType = "Ciężkie"

    return weightType

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
    try:
        return get_object_or_404(models.Items, name=itemName).maxDurability 
    except:
        return "?"

@register.filter
def getStaffMagicDmg(itemName, charId):
    char = get_object_or_404(models.Character, id=charId)
    item = get_object_or_404(models.Items, name=itemName)
    int = char.INT
    rarity = item.rarity

    if item.type=="Wand":
        dmg = 0
        dictionary_dmg = {
            "neutral-low": -7,
            "neutral-high": -6,
            "unique": -5,
            "magical": -4,
            "uncommon": -3,
        }
        dictionary_ap = {
            "neutral-low": 0,
            "neutral-high": 1,
            "unique": 2,
            "magical": 3,
            "uncommon": 4,
        }

        dmg = dictionary_dmg[rarity]+int
        if dmg > 0:
            dmg = f"+{dmg}"

        return f"[1K{dmg}, {dictionary_ap[rarity]}AP; Zasięg: 10]"
    else:
        return ""

    #return dmg based on type and character int 


@register.filter
def getItemType(itemName, translate="none"):
    
    translations_pl = {
        "Sword": "Miecz",
        "Axe": "Topór",
        "Dagger": "Sztylet",
        "Wand": "Kostur",
        "shield": "Tarcza",
        "Pistol": "Pistolet",
        "Hammer": "Młot",
        "SingleHand": "Jednoręczne",
        "Mace": "Buzdygan",
        "Spear": "Włócznia",
        "knuckles": "kastet",
        "Saber": "Szabla",
        "Shield": "Tarcza",
        "Halberd": "Halabarda",
        "Crossbow": "Kusza",
        "Staff": "Laska",
        "Musket": "Muszkiet",
        "Lute": "Lutnia",
        "Bow": "Łuk",
        "Helmet": "Hełm",
        "Torso": "Napierśnik",
        "Boots": "Buty",
        "Gloves": "Karwasze"
    }

    type = get_object_or_404(models.Items, name=itemName).type
    if translate=="none":
        return type
    elif translate=="pl":
        try:
            return translations_pl[type]
        except:
            return type

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
def getSkillAndDesc(itemName):
    try:
        limit = 80
        row = models.Items.objects.filter(name=itemName).get()
        skill = row.skill
        desc = row.desc

        if not skill or skill == "":
            full = desc
        else:
            full = f"{skill} | {desc}"

        if len(full)>limit:
            return full[:limit]+"..."
        return full

    except Exception as e:
        print(e)
        return False

@register.filter
def getDescId(itemName):
    try:
        return models.Items.objects.filter(name=itemName).values()[0]['id']
    except:
        return ''
   
@register.filter
def getItemDesc(itemName):
    try:
        limit = 80
        full_desc = models.Items.objects.filter(name=itemName).values()[0]['desc']
        if len(full_desc)>limit:
            return full_desc[:limit]+"..."
        return full_desc
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
        armor = ['helmet','armor','torso','boots','gloves','amulet', 'mount armor']
        if models.Items.objects.all().filter(name=itemName).values()[0]['type'].lower() in armor:
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

@register.filter
def rightItemNotAllowed(character):
    char = get_object_or_404(models.Character, name=character)
    skills = models.Skills.objects.filter(character=char.name)

    try:
        leftItem = models.CharItems.objects.filter(character=char.name, hand="Left").first()
        leftItemDesc = get_object_or_404(models.Items, name=leftItem.name)
    except:
        return False

    allowing_skills = {
        "wojskowe przeszkolenie": ["spear", "halberd", "glaive"]
    }

    allowing_classes = [
        "Paladyn: Przysięga Miecza",
        "Barbarzyńca: Droga Rosomaka"
        ""
    ]

    if char.chosen_class in allowing_classes:
        return False

    for skill in skills:
        if skill.skill.lower() in allowing_skills.keys():
            print(leftItemDesc.type.lower(), allowing_skills[skill.skill.lower()])
            if leftItemDesc.type.lower() not in allowing_skills[skill.skill.lower()]:
                return True
            return False
    
    if not leftItemDesc.dualHanded:
        return False
    
    return True


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
def getDurabilityPercent(itemName, currentDurability):
    maxDur = getMaxDurability(itemName)
    raw_perc = float(currentDurability)/float(maxDur)
    perc = format(raw_perc, '.0%')
    return f"({perc})"

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
            desc_armor = models.Items.objects.filter(name=item.name).first().armor
            if desc_armor != 0:
                armor += math.ceil(item.durability / 50)
            #armor += models.Items.objects.filter(name=item.name).first().armor - OLD
        except:
            pass
    
    return armor

@register.filter
def getArmorWeight(charName):
    char = get_object_or_404(models.Character, name=charName)
    helmet = models.CharItems.objects.filter(character=charName, position='Helmet').first()
    torso = models.CharItems.objects.filter(character=charName, position='Torso').first()
    boots = models.CharItems.objects.filter(character=charName, position='Boots').first()
    gloves = models.CharItems.objects.filter(character=charName, position='Gloves').first()
    amulets = models.CharItems.objects.filter(character=charName, position='Amulet').first()
    items = [helmet,torso,boots,gloves,amulets]  
    
    weight = 0

    types = { #first index for light armor, second for medium and above is heavy armor
    "Helmet": [1.5, 2.5],
    "Torso": [4,7],
    "Boots": [0.5, 1.1],
    "Gloves": [1, 2]
    }

    ignore_classes = {
        "paladyn: przysięga niewzruszonego": {"light": "full", "medium": "full", "heavy": "half"},
        "paladyn: przysięga obrońcy uciśnionych": {"light": "half", "medium": "half", "heavy": "half"},
        "paladyn: przysięga miecza": {"light": "half", "medium": "half", "heavy": "half"},
        "upadły paladyn: przysięga niewzruszonego": {"light": "5x", "medium": "5x", "heavy": "5x"},
        "upadły paladyn: przysięga obrońcy uciśnionych": {"light": "2x", "medium": "2x", "heavy": "2x"},
    }

    for item in items:
        try:
            item_desc = models.Items.objects.filter(name=item.name).first()

            type = types[f"{item_desc.type}"]
            if item_desc.weight < type[0]:
                wg_type = "light"
            elif item_desc.weight < type[1]:
                wg_type = "medium"
            else:
                wg_type = "heavy"

            char_class = char.chosen_class.lower()
            if char_class in ignore_classes:
                bonus = ignore_classes[char_class][wg_type]
                if bonus == "full":
                    weight += 0
                elif bonus == "half":
                    weight += item_desc.weight//2
                else:
                    weight += item_desc.weight * int(bonus[0])
            else:
                weight += item_desc.weight
        except:
            pass
        
    return weight 

@register.filter
def dict_get(d, key):
    if d is None:
        return ""
    try:
        return d.get(key, "")
    except AttributeError:
        return ""

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
def getItemRange(item_name):
    try:
        item = models.Items.objects.filter(name=item_name).first()
        twohanded = item.dualHanded
        type = item.type.lower()
        bonus = 0

        ranges = {
            "pistol": 9,
            "crossbow": 16,
            "heavy crossbow": 17,
            "arbalest": 18,
            "bow": 14,
            "longbow": 16,
            "musket": 18,
            "lute": 1,
            "shield": 1,
            "strzelba": 8,
            "krótka strzelba": 5,
            "wand": 15
        }

        if type in ranges.keys():
            return ranges[type]
        
        polearms = ["halberd", "spear", "glaive", "trident", "broń drzewcowa"]
        if type in polearms:
            bonus += 1

        if twohanded:
            return 2+bonus
        else:
            return 1+bonus
    except:
        return "?"

@register.filter
def getCharacterName(char_id):
    character = models.Character.objects.filter(id=char_id).first()
    try:
        return character.name
    except:
        return "No character"
    
@register.filter
def getCharacterItems(char_name):
    items = models.CharItems.objects.filter(character=char_name).values()

    return items

#CHARACTER-IS
@register.filter
def isNotEmpty(hand):
    if len(hand)>0:
        return True
    else:
        return False
