from django.contrib import admin
from . import models

admin.site.register(models.Users)
admin.site.register(models.NPC)
admin.site.register(models.Character)
admin.site.register(models.Mods)
admin.site.register(models.Eq)
admin.site.register(models.Skills)
admin.site.register(models.Skills_Decs)
admin.site.register(models.Items)
admin.site.register(models.CharItems)
admin.site.register(models.Races)
admin.site.register(models.Effects)
admin.site.register(models.Effects_Decs)