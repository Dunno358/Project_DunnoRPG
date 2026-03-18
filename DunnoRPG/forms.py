from django import forms
from django.forms import ModelForm
from DunnoRPG.models import Users, Character, Skills, Skills_Decs, Races, Eq, Items, Effects, Effects_Decs, Classes
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(forms.Form):
    name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.CharField(max_length=10)

    class Meta:
        model = Users
        fields = ["name","password","role"]
        
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
        
class AddEqItemForm(forms.ModelForm):
    character = forms.ChoiceField(choices=[],label='',widget=forms.Select(attrs={
        'class': 'text-center bg-dark rounded border border-warning c-gold p-1 m-1'
    }))
    
    name = forms.ChoiceField(choices=[],label='',widget=forms.Select(attrs={
        'class': 'text-center bg-dark rounded border border-info c-gold p-1 m-1'
    }))  
    
    durability = forms.IntegerField(label='dur',widget=forms.NumberInput(attrs={
        'class': 'text-center bg-dark c-gold rounded border border-info m-1',
        'value': 50,
        'min': 1
    }))  
    
    amount = forms.IntegerField(label='amount',widget=forms.NumberInput(attrs={
        'class': 'text-center bg-dark c-gold rounded border border-info m-1 w-75',
        'value': 1,
        'min': 1
    }))  
    
    override = forms.BooleanField(required=False,label='override_weight',widget=forms.CheckboxInput(attrs={
        'class': '',
        'name': 'override'
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['character'].choices = [
            (character.id, character.name)
            for character in Character.objects.filter(hidden=False).order_by('name')
        ]
        self.fields['name'].choices = [
            (item.id, item.name)
            for item in Items.objects.all().order_by('name')
        ]
    
    class Meta: 
        model = Eq
        fields = ['character','name','durability','amount']

class AddEffectForm(forms.ModelForm):
    characters = []
    try:
        for character in Character.objects.filter(hidden=False).order_by('name'):
            characters.append((character.id, character.name))
    except:
        pass
    character = forms.ChoiceField(choices=characters,label='',widget=forms.Select(attrs={
        'class': 'text-center bg-dark rounded border border-warning c-gold p-1 m-1'
    }))

    effects = []
    for effect in Effects_Decs.objects.all().order_by('name'):
        effects.append((effect.id, effect.name))
    name = forms.ChoiceField(choices=effects,label='',widget=forms.Select(attrs={
        'class': 'text-center bg-dark rounded border border-info c-gold p-1 m-1'
    })) 

    bonus = forms.IntegerField(label='Bonus',widget=forms.NumberInput(attrs={
        'class': 'text-center bg-dark c-gold rounded border border-info m-1 w-50',
        'value': 0,
    }))  

    time = forms.IntegerField(label='Time',widget=forms.NumberInput(attrs={
        'class': 'text-center bg-dark c-gold rounded border border-info m-1 w-50',
        'value': 1,
        'min': 1
    }))  

    class Meta:
        model = Effects
        fields = ['character', 'name','bonus','time']    
