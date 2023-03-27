from django import forms
from django.forms import ModelForm
from DunnoRPG.models import Users
from DunnoRPG.models import Character
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
        'value': 'test_value',
        'class': 'text-center ms-1 invisible'
    }))

    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': "Character's name",
        'class': 'ms-2'
    }))

    races = [('Human(Empire)', 'Human(Empire)'),
              ('Orc','Orc'),
                ('Dwarf', 'Dwarf'),
                  ('Vampire','Vampire'),
                    ('Elf','Elf'),
                    ('Human(Bretonnia)', 'Human(Bretonnia)')
                    ]
    race = forms.ChoiceField(choices=races)

    sizes = [('S', 'S'), ('M','M'), ('L','L')]
    size = forms.ChoiceField(choices=sizes)

    HP = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'value': 25,
        'class': 'w-25 ms-3'
    }))

    INT = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-25 ms-3'
    }))

    SIŁ = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-25 ms-3'
    }))

    ZRE = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-25 ms-2'
    }))

    CHAR = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-25'
    }))

    CEL = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-25 ms-2'
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