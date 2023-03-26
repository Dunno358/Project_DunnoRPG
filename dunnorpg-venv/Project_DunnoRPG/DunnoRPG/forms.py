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
        'value': 'test'
    }))

    class Meta:
        model = Character
        fields = ['owner']