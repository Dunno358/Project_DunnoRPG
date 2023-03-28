from django.db import models

class NPC(models.Model):
    Health_Points = models.CharField(max_length=255)
    Armor_Points = models.CharField(max_length=255)

class Users(models.Model):
    name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=10)

class Character(models.Model):
    owner = models.CharField(max_length=100)
    name = models.CharField(max_length=50)
    race = models.CharField(max_length=20)
    size = models.CharField(max_length=2)
    HP = models.IntegerField()
    Helmet = models.CharField(max_length=50)
    Torso = models.CharField(max_length=50)
    Gloves = models.CharField(max_length=50)
    Boots = models.CharField(max_length=50)
    LeftHand = models.CharField(max_length=50)
    RightHand = models.CharField(max_length=50)
    Side = models.CharField(max_length=50)
    INT = models.IntegerField()
    SIŁ = models.IntegerField()
    ZRE = models.IntegerField()
    CHAR = models.IntegerField()
    CEL = models.IntegerField()

class Mods(models.Model):
    owner = models.CharField(max_length=50)
    character = models.CharField(max_length=50)
    INT = models.IntegerField()
    SIŁ = models.IntegerField()
    ZRE = models.IntegerField()
    CHAR = models.IntegerField()
    CEL = models.IntegerField()

class Eq(models.Model):
    owner = models.CharField(max_length=50)
    character = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    weight = models.DecimalField(decimal_places=1, max_digits=50)

class Skills(models.Model):
    owner = models.CharField(max_length=50)
    character = models.CharField(max_length=50)
    skill = models.CharField(max_length=50)
    level = models.IntegerField(null=True)
    desc = models.TextField()

class Items(models.Model):
    name = models.CharField(max_length=50)
    desc = models.TextField()
    found = models.BooleanField()
    stats = models.CharField(max_length=50)
    skill = models.TextField()
    weight = models.DecimalField(decimal_places=1, max_digits=50)

# Create your models here.
