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

    owner = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'value': 'test_value',
        'class': 'text-center ms-1'
    }))

    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': "Character's name",
        'class': 'ms-2'
    }))

    races = [('1', 'Human(Empire)'),
              ('2','Orc'),
                ('3', 'Dwarf'),
                  ('4','Vampire'),
                    ('5','Elf'),
                    ('6', 'Human(Bretonnia)')
                    ]
    race = forms.ChoiceField(choices=races)

    sizes = [('1', 'S'), ('2','M'), ('3','L')]
    size = forms.ChoiceField(choices=sizes)

    HP = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'value': 25,
        'class': ''
    }))

    Helmet = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    Torso = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    Gloves = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    Boots = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    LeftHand = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    RightHand = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    Side = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    INT = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    SIŁ = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    ZRE = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    CHAR = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))

    CEL = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': ''
    }))



    class Meta:
        model = Character
        fields = [
            'owner',
            'name',
            'race',
            'size',
            'HP', 
            'Helmet', 
            'Torso', 
            'Gloves', 
            'Boots',
            'LeftHand',
            'RightHand',
            'Side',
            'INT',
            'SIŁ',
            'ZRE',
            'CHAR',
            'CEL'
            ]