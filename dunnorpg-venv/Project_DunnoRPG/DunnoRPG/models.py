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
    fullHP = models.IntegerField(null=True)
    Helmet = models.CharField(max_length=50, blank=True)
    Torso = models.CharField(max_length=50, blank=True)
    Gloves = models.CharField(max_length=50, blank=True)
    Boots = models.CharField(max_length=50, blank=True)
    LeftHand = models.CharField(max_length=50, blank=True)
    RightHand = models.CharField(max_length=50, blank=True)
    Side = models.CharField(max_length=50, blank=True)
    INT = models.IntegerField()
    SIŁ = models.IntegerField()
    ZRE = models.IntegerField()
    CHAR = models.IntegerField()
    CEL = models.IntegerField()
    points_left = models.IntegerField(null=True)

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
    category = models.CharField(max_length=50, null=True)
    level = models.IntegerField(null=True)
    desc = models.TextField()

class Skills_Decs(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length = 50, null = True)
    desc = models.TextField()
    level1 = models.TextField(null=True)
    need1_1 = models.CharField(max_length=20, null=True, blank=True)
    need1_2 = models.CharField(max_length=20, null=True, blank=True)
    level2 = models.TextField(null=True, blank=True)
    need2_1 = models.CharField(max_length=20, null=True, blank=True)
    need2_2 = models.CharField(max_length=20, null=True, blank=True)
    level3 = models.TextField(null=True, blank=True)
    need3_1 = models.CharField(max_length=20, null=True, blank=True)
    need3_2 = models.CharField(max_length=20, null=True, blank=True)
    level4 = models.TextField(null=True, blank=True)
    need4_1 = models.CharField(max_length=20, null=True, blank=True)
    need4_2 = models.CharField(max_length=20, null=True, blank=True)
    cost = models.CharField(max_length=20, null=True, blank=True)
    useAmount = models.IntegerField(null=True, blank=True)

class Items(models.Model):
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=50, null=True)
    desc = models.TextField()
    found = models.BooleanField()
    stats = models.CharField(max_length=50)
    skill = models.TextField(blank=True)
    weight = models.DecimalField(decimal_places=1, max_digits=50)
