from django.contrib import admin
from . import models

admin.site.register(models.Users)

admin.site.register(models.NPC)

admin.site.register(models.Character)

admin.site.register(models.Mods)

admin.site.register(models.Eq)

class SkillsAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('character','skill')
admin.site.register(models.Skills,SkillsAdmin)

class SkillDescAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('name','category')
admin.site.register(models.Skills_Decs, SkillDescAdmin)

class ItemsAdmin(admin.ModelAdmin):
    list_display = ("name", "rarity",'dualHanded','found','price')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('name','rarity')
admin.site.register(models.Items, ItemsAdmin)

class CharItemsAdmin(admin.ModelAdmin):
    list_display = ("character", "name", 'durability', ('maxDurability'), 'hand', 'position')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('character','name')
    def maxDurability(self, obj):
        return models.Items.objects.filter(name=obj.name).first().maxDurability
admin.site.register(models.CharItems, CharItemsAdmin)

admin.site.register(models.Races)

class EffectsAdmin(admin.ModelAdmin):
    list_display = ("character", "name", 'bonus', 'time')
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('character','name')
admin.site.register(models.Effects, EffectsAdmin)

admin.site.register(models.Effects_Decs)

class RequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "title", 'model', ('character_name'))
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('from_user')
    def character_name(self,obj):
        try:
            return models.Character.objects.filter(id=obj.char_id).first().name
        except:
            return None

admin.site.register(models.Requests, RequestAdmin)