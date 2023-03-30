from django import forms
from django.forms import ModelForm
from DunnoRPG.models import Users
from DunnoRPG.models import Character
from DunnoRPG.models import Skills
from DunnoRPG.models import Skills_Decs
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(forms.Form):
    name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.CharField(max_length=10)

    class Meta:
        model = Users
        fields = ["name","password","role"]

class CharacterForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self._user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    owner = forms.CharField(max_length=100,label='' ,widget=forms.TextInput(attrs={
        'value': 'owner will be added automatically',
        'class': 'text-center ms-1 invisible'
    }))

    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': "Character's name",
        'class': 'ms-2 text-center'
    }))

    races = [('Human(Empire)', 'Human(Empire)'),
              ('Orc','Orc'),
                ('Dwarf', 'Dwarf'),
                  ('Vampire','Vampire'),
                    ('Elf','Elf'),
                    ('Human(Bretonnia)', 'Human(Bretonnia)'),
                    ('Human(Kislev)', 'Human(Kislev)'),
                    ('Goblin', 'Goblin'),
                    ('High Elven (Asurii)', 'High Elven (Asurii)'),
                    ('Athel Loren Elven', 'Athel Loren Elven'),
                    ('Halfling', 'Halfling'),
                    ('Gnome', 'Gnome'),
                    ('Half-orc', 'Half-orc'),
                    ('Half-elf', 'Half-elf'),
                    ('Ogre', 'Ogre'),
                    ('Satyr', 'Satyr')
                    ]
    races.sort()
    race = forms.ChoiceField(choices=races,widget=forms.Select(attrs={
        'class': 'text-center'
    }))

    size = forms.CharField(max_length=1,label='' ,widget=forms.TextInput(attrs={
        'value': 'M',
        'class': 'text-center ms-1 invisible'
    }))

    HP = forms.CharField(max_length=5,label='', widget=forms.TextInput(attrs={
        'value': 25,
        'class': 'w-25 ms-3 invisible'
    }))

    INT = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-3 text-center',
        'value': 0
    }))

    SIŁ = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-3 text-center',
        'value': 0
    }))

    ZRE = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-2 text-center',
        'value': 0
    }))

    CHAR = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'w-25 text-center',
        'value': 0
    }))

    CEL = forms.IntegerField(widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-2 text-center',
        'value': 0
    }))



    class Meta:
        model = Character
        fields = [
            'owner',
            'name',
            'race',
            'size',
            'HP', 
            'INT',
            'SIŁ',
            'ZRE',
            'CHAR',
            'CEL'
            ]
        
class CharacterSkillsForm(forms.ModelForm):

    skills_choices = list(Skills_Decs.objects.all().values('name'))
    for x in range(len(skills_choices)):
        skills_choices[x] = (skills_choices[x]['name'], skills_choices[x]['name'])

    skill = forms.ChoiceField(choices=skills_choices, widget=forms.Select(attrs={
        'class': 'me-4 border border-warning bg-dark text-white-50 rounded'
    }))

    lvls = [('1','1'),('2','2'),('3','3'),('4','4')]
    level = forms.ChoiceField(choices=lvls,widget=forms.Select(attrs={
        'class': 'w-10 ps-3 border border-warning bg-dark text-white-50 rounded'
    }))

    owner = forms.CharField(max_length=50,label='',widget=forms.TextInput(attrs={
        'value': 'owner will be added automatically',
        'class': 'invisible'
    }))

    class Meta:
        model = Skills
        fields = [
            'skill',
            'level',
            'owner'
        ]