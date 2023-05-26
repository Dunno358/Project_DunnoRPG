from django import forms
from django.forms import ModelForm
from DunnoRPG.models import Users
from DunnoRPG.models import Character
from DunnoRPG.models import Skills
from DunnoRPG.models import Skills_Decs
from DunnoRPG.models import Races
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
        'class': 'ms-2 text-center rounded'
    }))

    query_races = Races.objects.all().values()
    races = []
    races.append(('Choose a race','Choose a race'))
    for race in query_races:
        races.append((race['name'], race['name']))
    races.sort()
    race = forms.ChoiceField(choices=races,widget=forms.Select(attrs={
        'class': 'text-center border border-warning bg-dark text-white-50 rounded'
    }))

    size = forms.CharField(max_length=50,label='' ,widget=forms.TextInput(attrs={
        'value': 'M',
        'class': 'text-center ms-5 invisible bg-transparent w-25'
    }))

    HP = forms.CharField(max_length=5,label='', widget=forms.TextInput(attrs={
        'value': 25,
        'class': 'w-25 ms-3 invisible'
    }))

    INT = forms.IntegerField(label='(+0) INT:',widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-3 text-center rounded',
        'value': 0,
        'min': 0
    }))

    SIŁ = forms.IntegerField(label='(+0) SIŁ:',widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-3 text-center rounded',
        'value': 0,
        'min': 0
    }))

    ZRE = forms.IntegerField(label='(+0) ZRE:',widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-2 text-center rounded',
        'value': 0,
        'min': 0
    }))

    CHAR = forms.IntegerField(label='(+0) CHAR:',widget=forms.NumberInput(attrs={
        'class': 'w-25 text-center rounded',
        'value': 0,
        'min': 0
    }))

    CEL = forms.IntegerField(label='(+0) CEL:',widget=forms.NumberInput(attrs={
        'class': 'w-25 ms-2 text-center rounded',
        'value': 0,
        'min': 0
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
    skills_choices = sorted(skills_choices)

    skill = forms.ChoiceField(choices=skills_choices,label='',widget=forms.Select(attrs={
        'class': 'text-center w-75 border border-warning bg-dark text-white-50 rounded'
    }))

    lvls = [('1','1'),('2','2'),('3','3'), ('4','4')]
    level = forms.ChoiceField(choices=lvls,label='',widget=forms.Select(attrs={
        'class': 'text-center w-15 border border-warning bg-dark text-white-50 rounded'
    }))

    owner = forms.CharField(max_length=50,label='',widget=forms.TextInput(attrs={
        'value': 'o',
        'class': 'invisible w-0'
    }))

    class Meta:
        model = Skills
        fields = [
            'skill',
            'level',
            'owner'
        ]
