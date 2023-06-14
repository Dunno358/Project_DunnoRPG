from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from DunnoRPG import models


class UpgradeCharacterStatsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client = APIClient()
        self.client.login(username='testuser', password='testpassword')
        
        self.characters = []
        for x in range(5):
            self.character = models.Character.objects.create(
                id=x+1, 
                owner = 'testuser',
                name = f'testcharacter{x+1}',
                race = 'Człowiek(Imperium)',
                size = 'M',
                HP= 25,
                fullHP = 25,
                INT = 1,
                SIŁ = 1,
                ZRE = 1,
                CHAR = 1,
                CEL = 1,
                points_left=1)
            self.characters.append(self.character)
        
    def test_is_response_OK(self):
        url = reverse('stat-upgrade', kwargs={'char_id': self.characters[0].id, 'stat': 'INT'})

        response = self.client.get(url, follow=True)
        
        self.assertEqual(response.status_code, 200)        
        
    def test_is_stat_upgraded(self):
        char_stats = ['INT', 'SIŁ' ,'ZRE', 'CHAR', 'CEL']
        for char_stat in char_stats:
            index = char_stats.index(char_stat)
            url = reverse('stat-upgrade', kwargs={'char_id': self.characters[index].id, 'stat': char_stat})

            response = self.client.get(url, follow=True)
            
            self.characters[index].refresh_from_db()
            
            self.assertEqual(getattr(self.characters[index], char_stat), 2)
            self.assertEqual(self.characters[index].points_left, 0)    
            
    def test_insufficient_points(self):
        for x in range(len(self.characters)):
            self.characters[x].points_left = 0
            self.characters[x].save()
        char_stats = ['INT', 'SIŁ' ,'ZRE', 'CHAR', 'CEL']
        for char_stat in char_stats:
            index = char_stats.index(char_stat)
            url = reverse('stat-upgrade', kwargs={'char_id': self.characters[index].id, 'stat': char_stat})

            response = self.client.get(url, follow=True)
            
            self.characters[index].refresh_from_db()
            
            self.assertEqual(self.characters[index].points_left, 0) 
            self.assertEqual(getattr(self.characters[index], char_stat), 1)
            
    def test_invalid_char_id_response(self):
        url = reverse('stat-upgrade', kwargs={'char_id': 199999, 'stat': 'INT'})
        response = self.client.get(url, follow=True)  
        self.assertEqual(response.status_code, 404)   
        
    def test_invalid_star_response(self):
        url = reverse('stat-upgrade', kwargs={'char_id': 1, 'stat': 'Inteligencja'})
        response = self.client.get(url, follow=True)  
        self.assertEqual(response.status_code, 404)     
        
    def test_is_redirect_OK(self):
        for x in range(len(self.characters)):
            url = reverse('stat-upgrade', kwargs={'char_id': self.characters[x].id, 'stat': 'INT'})
            response = self.client.get(url)
            
            self.assertRedirects(response, f"/dunnorpg/character_add_skills/{self.characters[x].id}/")

class SkillUpgradeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.magical_skill = models.Skills.objects.create(
            id=1,
            owner = 'testowner1',
            character = 'testcharacter1',
            skill = 'Kula ognia',
            category = 'Magical',
            level = 1,
            desc = 'testdesc'
        )
        
        self.magical_skill_desc = models.Skills_Decs.objects.create(
            id=1,
            name = 'Kula ognia',
            category = 'Magical',
            desc = 'TestDesc',
            level1 = 'l1desc',
            level2 = 'l2desc',
            level3 = 'l3desc',
            level4 = 'l4desc',
            cost = '1',
            useAmount = 2
        )
        
        self.normal_skill = models.Skills.objects.create(
            id=2,
            owner = 'testowner1',
            character = 'testcharacter1',
            skill = 'Cios berserkera',
            category = 'Melee',
            level = 1,
            desc = 'testdesc'
        )
        
        self.normal_skill_desc = models.Skills_Decs.objects.create(
            id=2,
            name = 'Cios berserkera',
            category = 'Melee',
            desc = 'TestDesc',
            level1 = 'l1desc',
            level2 = 'l2desc',
            need2_1= 'SIŁ3',
            level3 = 'l3desc',
            cost = '1',
            useAmount = 1
        )
        
        self.character = models.Character.objects.create(
            id=1, 
            owner = 'testuser',
            name = f'testcharacter1',
            race = 'Człowiek(Imperium)',
            size = 'M',
            HP= 25,
            fullHP = 25,
            INT = 3,
            SIŁ = 5,
            ZRE = 1,
            CHAR = 1,
            CEL = 1,
            points_left=4)
        
    def test_skill_upgrade_success(self):
        self.client.login(username='testuser', password='testpass')
        
        #Magical skill
        url = reverse('skill_upgrade', args=[self.character.id, self.magical_skill.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 302) #302 for redirect
        
        updated_skill = models.Skills.objects.get(id=self.magical_skill.id)
        self.assertEqual(updated_skill.level, 2)
        self.assertEqual(updated_skill.desc, f"{self.magical_skill_desc.desc} {self.magical_skill_desc.level2}")
        
        updated_character = models.Character.objects.get(id=self.character.id)
        self.assertEqual(updated_character.points_left, self.character.points_left) #shouldn't change
        
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages, []) #no error messages
        
        #Melee skill
        url = reverse('skill_upgrade', args=[self.character.id, self.normal_skill.id])
        response = self.client.post(url)   
        
        self.assertEqual(response.status_code, 302)
             
        updated_skill = models.Skills.objects.get(id=self.normal_skill.id)
        self.assertEqual(updated_skill.level, 2)
        self.assertEqual(updated_skill.desc, f"{self.normal_skill_desc.desc} {self.normal_skill_desc.level2}")
        
        updated_character = models.Character.objects.get(id=self.character.id)
        self.assertEqual(updated_character.points_left, self.character.points_left-1)
        
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(messages, []) #no error messages
            
    def test_max_lvl_reached(self):
        self.client.login(username='testuser', password='testpass')
        
        self.character.INT = 5 #making sure there will be enough INT for upgrading spells
        self.character.save()
        self.magical_skill.level = 4
        self.magical_skill.save()
        self.normal_skill.level = 3
        self.normal_skill.save()
        
        #Magical skill
        response = self.client.post(reverse('skill_upgrade', args=[self.character.id, self.magical_skill.id])) 
        self.assertEqual(response.status_code, 302) 
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f'{self.magical_skill.skill} maximum level reached!')   
        
        #Normal skill
        response2 = self.client.post(reverse('skill_upgrade', args=[self.character.id, self.normal_skill.id])) 
        self.assertEqual(response2.status_code, 302) 
        messages = list(get_messages(response2.wsgi_request))
        
        self.assertEqual(len(messages), 2)
        self.assertEqual(str(messages[1]), f'{self.normal_skill.skill} maximum level reached!')         

        
    def test_insufficient_points(self):
        self.client.login(username='testuser', password='testpass')
        self.character.INT = 1 #adding spell takes 1 point from INT so 2 INT is needed for upgrade
        self.character.points_left = 0
        self.character.save()
        
        #Magical skill
        response = self.client.post(reverse('skill_upgrade', args=[self.character.id, self.magical_skill.id]))
        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f'Not enough points to upgrade {self.magical_skill.skill}.')   
        
        #Normal skill
        response2 = self.client.post(reverse('skill_upgrade', args=[self.character.id, self.normal_skill.id]))
        self.assertEqual(response2.status_code, 302)
        messages = list(get_messages(response2.wsgi_request))
        self.assertEqual(len(messages), 2)
        self.assertEqual(str(messages[1]), f'Not enough points to upgrade {self.normal_skill.skill}.')  
        
    def test_insufficient_stats(self):
        self.character.SIŁ = 1
        self.character.save()
        self.client.login(username='testuser', password='testpass')     
        
        response = self.client.post(reverse('skill_upgrade', args=[self.character.id, self.normal_skill.id]))
        self.assertEqual(response.status_code, 302)
        
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), f'Your stats are too low to upgrade {self.normal_skill.skill}, you need SIŁ(3)') 
        
#Skill downgrade API to be tested next