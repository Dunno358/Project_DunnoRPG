from . import models
from rest_framework import serializers

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Items
        fields = ['id','name','type','desc','found','stats','skill','weight']

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Character
        fields = '__all__'
    def create(self,validated_data):
        return models.Character.objects.create(**validated_data)
        
class SkillsDecsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Skills_Decs
        fields = ['id','name','category','desc',
                  'level1','need1_1','need1_2',
                  'level2','need2_1','need2_2',
                  'level3','need3_1','need3_2',
                  'level4','need4_1','need4_2',
                  'cost','useAmount'
                  ]
        
class SkillsSerializer(serializers.ModelSerializer):
    model = models.Skills
    fields = [
        'id', 'owner', 'character', 'skill', 'category', 'level', 'desc'
    ]
    def create(self,validated_data):
        return models.Skills.objects.create(**validated_data)

class EqSerializer(serializers.ModelSerializer):
    model = models.Eq
    fields = [
        'owner', 'character', 'name', 'weight'
    ]

class ModsSerializer(serializers.ModelSerializer):
    model = models.Mods
    fields = [
        'id','owner','character','INT','SIŁ','ZRE','CHAR','CEL'
    ]