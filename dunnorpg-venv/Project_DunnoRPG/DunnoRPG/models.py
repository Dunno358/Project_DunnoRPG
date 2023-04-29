from django.db import models
from pygments.lexers import get_lexer_by_name
from pygments.formatters.html import HtmlFormatter
from pygments import highlight

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
    race = models.CharField(max_length=30)
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
    weaponBonus = models.IntegerField(null=True)
    preferredWeapons = models.TextField(blank=True)
    unlikedWeapons = models.TextField(blank=True)
    

    def __str__(self):
        return f"{self.name} ({self.id})"

class Mods(models.Model):
    owner = models.CharField(max_length=50, null=True)
    character = models.CharField(max_length=50, null=True)
    field = models.CharField(max_length=10, default='INT')
    value = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.character} | {self.field}: {self.value}"

class Races(models.Model):
    name = models.CharField(max_length=100)
    size = models.CharField(max_length=5)
    statPlus = models.CharField(max_length=255,blank=True)
    statMinus = models.CharField(max_length=255,blank=True)
    Skills = models.CharField(max_length=255,blank=True)
    points_limit = models.IntegerField(null=True)
    desc = models.TextField(blank=True)
    def __str__(self):
        return self.name

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
    desc = models.TextField(blank=True)

    def __str__(self):
        return f"{self.character}: {self.skill} lvl.{self.level}"

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

    def __str__(self):
        return self.name

class Items(models.Model):
    name = models.CharField(max_length=50, null=True)
    type = models.CharField(max_length=50, null=True)
    dualHanded = models.BooleanField(default=False)
    desc = models.TextField(null=True)
    found = models.BooleanField(default=False)
    stats = models.CharField(max_length=50, default='1K+0, 0AP')
    skill = models.TextField(blank=True)
    weight = models.DecimalField(decimal_places=1, max_digits=50, default=1)

    def __str__(self):
        return self.name
    
class Effects(models.Model):
    owner = models.CharField(max_length = 150)
    character = models.CharField(max_length = 150)
    name = models.CharField(max_length = 150)
    category = models.CharField(max_length = 150, null=True)
    desc = models.TextField()
    time = models.CharField(max_length=10)
    def __str__(self):
        return f"{self.character}: {self.name} ({self.time})"
    
    

    
