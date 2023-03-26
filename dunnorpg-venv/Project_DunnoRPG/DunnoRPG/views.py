from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from . import models
from .forms import CharacterForm

def home(request):
    current_user = request.user
    avaible_characters = models.Character.objects.all().filter(owner=current_user)
    context = {
        'characters': avaible_characters,
        'characters_count': len(avaible_characters)
    }
    return render(request, "home.html", context)

def character_detail(request, id):
    current_user = request.user
    chosen = models.Character.objects.all().filter(owner=current_user, id=id)
    context = {
        'chosen_character': chosen
    }
    return render(request, "character_detail.html", context)

def character_add(request):
    current_user = request.user
    form = CharacterForm(request.POST, user=current_user)
    context = {
        'form': form,
        'user': current_user
    }
    return render(request, "character_add.html", context)

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"