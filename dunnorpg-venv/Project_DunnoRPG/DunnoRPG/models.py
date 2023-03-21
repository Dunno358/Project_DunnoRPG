from django.db import models

class NPC(models.Model):
    Health_Points = models.CharField(max_length=255)
    Armor_Points = models.CharField(max_length=255)

# Create your models here.
