from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
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
            