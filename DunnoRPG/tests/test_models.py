from django.test import TestCase
from DunnoRPG import models

#
class CharacterModelTest(TestCase):
    def setUp(self):
        models.Character.objects.create(
            owner='John',
            name='Character 1',
            race='Human',
            size='M',
            HP=25,
            fullHP=25,
            Helmet='Helmet 1',
            Torso='Torso 1',
            Gloves='Gloves 1',
            Boots='Boots 1',
            Side='Side 1',
            INT=10,
            SIŁ=8,
            ZRE=6,
            CHAR=4,
            CEL=2,
            points_left=5,
            weaponBonus=2,
            preferredWeapons='Sword;Bow',
            unlikedWeapons='Axe'            
        )
        
    def test_objects_str_representation(self):
        self.character = models.Character.objects.get(name='Character 1')
        expected_representation = f"John: Character 1 (1)"
        self.assertEqual(str(self.character),expected_representation)
        
    def test_object_attributes(self):
        character = models.Character.objects.get(name='Character 1')
        self.assertEqual(character.owner, 'John')
        self.assertEqual(character.race, 'Human')
        self.assertEqual(character.size, 'M')
        self.assertEqual(character.HP, 25)
        self.assertEqual(character.fullHP, 25)
        self.assertEqual(character.Helmet, 'Helmet 1')
        self.assertEqual(character.Torso, 'Torso 1')
        self.assertEqual(character.Gloves, 'Gloves 1')
        self.assertEqual(character.Boots, 'Boots 1')
        self.assertEqual(character.Side, 'Side 1')
        self.assertEqual(character.INT, 10)
        self.assertEqual(character.SIŁ, 8)
        self.assertEqual(character.ZRE, 6)
        self.assertEqual(character.CHAR, 4)
        self.assertEqual(character.CEL, 2)
        self.assertEqual(character.points_left, 5)
        self.assertEqual(character.weaponBonus, 2)
        self.assertEqual(character.preferredWeapons, 'Sword;Bow')
        self.assertEqual(character.unlikedWeapons, 'Axe')
        
    def test_update(self):
        character = models.Character.objects.get(name='Character 1')
        character.name = 'Character 1 Updated'
        character.CEL = 8
        
        character.save()
        
        updated_character = models.Character.objects.get(pk=character.pk)
        self.assertEqual(updated_character.name, 'Character 1 Updated')
        self.assertEqual(updated_character.CEL, 8)
        
    def test_delete(self):
        character = models.Character.objects.get(name='Character 1')
        character.delete()
        
        self.assertFalse(models.Character.objects.filter(pk=character.pk).exists())
        
    def test_validation(self):
        with self.assertRaises(ValueError):
            models.Character.objects.create(
                owner='John',
                name=44, #Invalid
                race='Human',
                size='M',
                HP='InvalidCase', #Invalid
                fullHP=25,
                Helmet='Helmet 1',
                Torso='Torso 1',
                Gloves='Gloves 1',
                Boots='Boots 1',
                Side='Side 1',
                INT=10,
                SIŁ=8,
                ZRE=6,
                CHAR=4,
                CEL=2,
                points_left=5,
                weaponBonus=2,
                preferredWeapons='Sword;Bow',
                unlikedWeapons='Axe'
            )            