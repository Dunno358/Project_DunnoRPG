from django import template
from DunnoRPG import models

register = template.Library()

@register.filter
def getItemStatByName(itemName):
    try:
        return models.Items.objects.all().filter(name=itemName).values()[0]['stats']
    except:
        pass

@register.filter
def getMod(character,stat_for_mod):
    value = 0
    for stat in models.Mods.objects.all().filter(character=character['name'], field=stat_for_mod).values():
        value += stat['value']
    if value>=0:
        value = f"+{value}"
    return value