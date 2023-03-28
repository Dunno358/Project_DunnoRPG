from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from . import models
from .forms import CharacterForm
from .forms import CharacterSkillsForm

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

    if request.method == 'POST':
        form = CharacterForm(request.POST, user=current_user)
        if form.is_valid():

            size_s = ['Dwarf','Goblin','Halfling','Gnome']
            size_m = ['Human(Empire)','Vampire','Elf','Human(Bretonnia)','Human(Kislev)','High Elven (Asurii)','Athel Loren Elven','Half-orc','Half-elf','Satyr']
            size_l = ['Orc','Ogre']

            character = form.save(commit=False)
            character.owner = current_user
            if character.race in size_s:
                character.size = 'S'
            elif character.race in size_m:
                character.size = 'M'
            else:
                character.size = 'L'
            character.save()
            return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{character.id}')
    else:
        form  = CharacterForm()

    context = {
        'form': form,
        'user': current_user
    }
    return render(request, "character_add.html", context)

def character_add_skills(request, id):
    current_user = request.user
    chosen_character = models.Character.objects.all().filter(owner=current_user, id=id)

    if request.method == 'POST':
        form = CharacterSkillsForm(request.POST)
        if form.is_valid():

            character_skills = form.save(commit=False)

            character_skills.save()
            return HttpResponseRedirect('/dunnorpg/')
    else:
        form = CharacterSkillsForm()

    context = {
        'user': current_user,
        'character': chosen_character,
        'form': form
    }
    return render(request, "character_add_skills.html", context)

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"