from . import models
from rest_framework import serializers

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Items
        fields = '__all__'

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Character
        fields = '__all__'
    def create(self,validated_data):
        return models.Character.objects.create(**validated_data)
        
class SkillsDecsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Skills_Decs
        fields = '__all__'
        
class SkillsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Skills
        fields = '__all__'

class EqSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Eq
        fields = '__all__'

class ModsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Mods
        fields = '__all__'