from django.db import models
from pygments.lexers import get_lexer_by_name
from pygments.formatters.html import HtmlFormatter
from pygments import highlight
from django.shortcuts import get_object_or_404

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
    chosen_class = models.CharField(max_length=80, default='', blank=True)
    size = models.CharField(max_length=2)
    HP = models.IntegerField()
    fullHP = models.IntegerField(null=True)
    coins = models.IntegerField(default=5)
    Helmet = models.CharField(max_length=50, blank=True)
    Torso = models.CharField(max_length=50, blank=True)
    Gloves = models.CharField(max_length=50, blank=True)
    Boots = models.CharField(max_length=50, blank=True)
    Side = models.CharField(max_length=50, blank=True)
    INT = models.IntegerField()
    SIŁ = models.IntegerField()
    ZRE = models.IntegerField()
    CHAR = models.IntegerField()
    CEL = models.IntegerField()
    points_left = models.IntegerField(null=True)
    weaponBonus = models.IntegerField(null=True)
    preferredWeapons = models.TextField(null=True)
    unlikedWeapons = models.TextField(null=True)
    extra_capacity = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    model_url = models.CharField(max_length=255, blank=True, null=True)
    hidden = models.BooleanField(default=False)
    

    def __str__(self):
        return f"{self.owner}: {self.name} ({self.id})"

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
    weaponsBonus = models.IntegerField(null=True)
    weaponsPreffered = models.CharField(max_length=255,blank=True,null=True)
    weaponsUnliked = models.CharField(max_length=255,blank=True,null=True)
    def __str__(self):
        return self.name

class Eq(models.Model):
    owner = models.CharField(max_length=100)
    character = models.CharField(max_length=80)
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=80, default='Other')
    weight = models.DecimalField(decimal_places=1, max_digits=50)
    durability = models.IntegerField(default=50)
    amount = models.IntegerField(default=1)

class Skills(models.Model):
    owner = models.CharField(max_length=50)
    character = models.CharField(max_length=50)
    skill = models.CharField(max_length=50)
    category = models.CharField(max_length=50, null=True)
    level = models.IntegerField(null=True)
    desc = models.TextField(blank=True)
    uses_left = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.character}: {self.skill} lvl.{self.level}"

class Skills_Decs(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length = 50, null = True)
    desc = models.TextField()
    level1 = models.TextField(null=True)
    need1_1 = models.CharField(max_length=20, null=True, blank=True)
    need1_2 = models.CharField(max_length=20, null=True, blank=True)
    useslvl1 = models.IntegerField(null=True, blank=True)
    level2 = models.TextField(null=True, blank=True)
    need2_1 = models.CharField(max_length=20, null=True, blank=True)
    need2_2 = models.CharField(max_length=20, null=True, blank=True)
    useslvl2 = models.IntegerField(null=True, blank=True)
    level3 = models.TextField(null=True, blank=True)
    need3_1 = models.CharField(max_length=20, null=True, blank=True)
    need3_2 = models.CharField(max_length=20, null=True, blank=True)
    useslvl3 = models.IntegerField(null=True, blank=True)
    level4 = models.TextField(null=True, blank=True)
    need4_1 = models.CharField(max_length=20, null=True, blank=True)
    need4_2 = models.CharField(max_length=20, null=True, blank=True)
    useslvl4 = models.IntegerField(null=True, blank=True)
    cost = models.CharField(max_length=20, null=True, blank=True)
    useAmount = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Items(models.Model):
    name = models.CharField(max_length=50, null=True)
    type = models.CharField(max_length=50, null=True)
    rarity = models.CharField(max_length=50, null=True)
    dualHanded = models.BooleanField(default=False)
    desc = models.TextField(null=True)
    found = models.BooleanField(default=False)
    diceBonus = models.IntegerField(default=0)
    AP = models.IntegerField(default=0)
    armor = models.IntegerField(default=0)
    block = models.IntegerField(default=0)
    skill = models.TextField(blank=True)
    skillStats = models.CharField(max_length=250, null=True, blank=True)
    skillEffects = models.CharField(max_length=250, null=True, blank=True)
    weight = models.DecimalField(decimal_places=1, max_digits=50, default=1)
    altAttack = models.CharField(max_length=250, default='None')
    maxDurability = models.IntegerField(default=50)
    neededAccuraccy = models.IntegerField(default=6)
    additionalInfo = models.TextField(blank=True,null=True)
    price = models.IntegerField(default=5)

    def __str__(self):
        if self.dualHanded == True:
            return f"{self.name} [Dual handed]"
        return f"{self.name}"
    
class CharItems(models.Model):
    owner = models.CharField(max_length = 80)
    character = models.CharField(max_length = 150)
    name = models.CharField(max_length = 150, null=True, blank=True)
    durability = models.IntegerField(default=50, null=True, blank=True)
    hand = models.CharField(max_length = 10, default='Left', null=True, blank=True)
    position = models.CharField(max_length = 20, null=True, blank=True)

    def __str__(self):
        max_durability = get_object_or_404(Items, name=self.name).maxDurability
        return f"[{self.character}] {self.name} ({self.durability}/{max_durability}) [{self.hand}]"
    
class Effects(models.Model):
    owner = models.CharField(max_length = 150)
    character = models.CharField(max_length = 150)
    name = models.CharField(max_length = 150)
    bonus = models.IntegerField(default=0)
    time = models.IntegerField(default=0)
    def __str__(self):
        return f"{self.character}: {self.name} ({self.time})"
    
class Effects_Decs(models.Model):
    types = (
        ('attack', 'attack'),
        ('parry', 'parry'),
        ('attack&parry', 'attack&parry'),
        ('dodge&parry', 'dodge&parry'),
        ('all','all'),
        ('other','other'),
        ('dodge','dodge'),
        ('agility','agility'),
        ('sneaking','sneaking'),
        ('resistance', 'resistance'),
        ('regeneration', 'regeneration'),
        ('armor', 'armor'),
        ('resting', 'resting'),
        ('poison','poison'),
        ('cel','cel')
    )
    
    name = models.CharField(max_length = 150)
    category = models.CharField(max_length = 150, choices=types)
    desc = models.TextField()
    bonus = models.IntegerField(default=0)
    time = models.IntegerField(default=0)
    def __str__(self):
        return self.name
    
class Requests(models.Model):
    from_user = models.CharField(max_length = 150)
    char_id = models.IntegerField(null=True)
    objects_model = models.CharField(max_length = 150, default='Items')
    object1_id = models.IntegerField(default=0)
    object2_id = models.IntegerField(default=0)
    model = models.CharField(max_length = 150)
    field = models.CharField(max_length = 150, null=True, blank=True)
    title = models.CharField(max_length = 150)
    
class Cities(models.Model):
    city_name = models.CharField(max_length = 150)
    items = models.TextField()
    magic_school = models.BooleanField(default=False)
    champion_school_type = models.CharField(max_length = 150)
    visiting = models.BooleanField(default=False)