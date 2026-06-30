from . import models
from rest_framework import serializers

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Items
        fields = '__all__'

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if not request or not request.user.is_superuser:
            fields.pop('hiddenSkill', None)
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not request.user.is_superuser:
            data.pop('hiddenSkill', None)
        return data

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
