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
    alert = 0

    if request.method == 'POST':
        form = CharacterForm(request.POST, user=current_user)
        if form.is_valid():

            size_s = ['Dwarf','Goblin','Halfling','Gnome']
            size_m = ['Human(Empire)','Vampire','Human(Bretonnia)','Human(Kislev)','High Elven (Asurii)','Athel Loren Elven','Half-orc','Half-elf','Satyr']
            size_l = ['Orc','Ogre']

            character = form.save(commit=False)
            character.owner = current_user

            if character.race == 'Human(Empire)':
                limit = 11
            else:
                limit = 10

            if character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL <= limit:
                if character.race in size_s:
                    character.size = 'S'
                elif character.race in size_m:
                    character.size = 'M'
                else:
                    character.size = 'L'

                races_mods = {
                    'Athel Loren Elven': {'int': -1, 'sil': 0, 'zre': 0, 'char': 0, 'cel': 0},
                    'Halfling': {'int': 0, 'sil': -2, 'zre': 0, 'char': 0, 'cel': 0},
                    'Gnome': {'int': 0, 'sil': -2, 'zre': 0, 'char': 0, 'cel': 0},
                    'Half-orc': {'int': -2, 'sil': 1, 'zre': -1, 'char': 0, 'cel': 0},
                    'Half-elf': {'int': 0, 'sil': -1, 'zre': 0, 'char': 0, 'cel': 0},
                    'Ogre': {'int': -1, 'sil': 3, 'zre': -3, 'char': 0, 'cel': 0},
                    'Satyr': {'int': -1, 'sil': 0, 'zre': 1, 'char': -1, 'cel': 0},
                    'High Elven (Asurii)': {'int': 0, 'sil': -1, 'zre': 0, 'char': -2, 'cel': 0},
                    'Orc': {'int': -3, 'sil': 2, 'zre': -2, 'char': 0, 'cel': 0},
                    'Goblin': {'int': 0, 'sil': -1, 'zre': 1, 'char': 0, 'cel': 0},
                    'Dwarf': {'int': 0, 'sil': -1, 'zre': 0, 'char': -2, 'cel': 0},
                    'Human(Kislev)': {'int': 0, 'sil': 0, 'zre': 0, 'char': 1, 'cel': 0},
                    'Human(Empire)': {'int': 0, 'sil': 0, 'zre': 0, 'char': 0, 'cel': 0},
                    'Human(Bretonnia)': {'int': 0, 'sil': 0, 'zre': 0, 'char': 0, 'cel': 0},
                    'Vampire': {'int': 0, 'sil': 0, 'zre': 0, 'char': 0, 'cel': 0},
                }

                for race in races_mods:
                    if character.race == race: 
                        character.INT += races_mods[race]['int']
                        character.SIŁ += races_mods[race]['sil']
                        character.ZRE += races_mods[race]['zre']
                        character.CHAR += races_mods[race]['char']
                        character.CEL += races_mods[race]['cel']
                
                character.save()
                return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{character.id}')
            else:
                alert = 1
                form = CharacterForm()
    else:
        form  = CharacterForm()

    context = {
        'form': form,
        'user': current_user,
        'alert': alert
    }
    return render(request, "character_add.html", context)

def character_add_skills(request, id):
    current_user = request.user
    chosen_character = list(models.Character.objects.all().filter(owner=current_user, id=id).values())[0]['name']
    character_skills_queryset = list(models.Skills.objects.filter(owner=current_user,character=chosen_character).values())
    character_skills = []

    for data in character_skills_queryset:
        character_skills.append({'skill': data['skill'], 'level': data['level']})
    
    print(character_skills)

    if request.method == 'POST':
        form = CharacterSkillsForm(request.POST)
        if form.is_valid():
            character_skills = form.save(commit=False)
            character_skills.owner = current_user
            character_skills.save()

            skill = models.Skills.objects.last()
            skill_desc = models.Skills_Decs.objects.filter(name=skill.skill).values()[0]['desc']

            skill.character = chosen_character
            skill.desc = skill_desc
            skill.save()
            return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{id}')
    else:
        form = CharacterSkillsForm()

    context = {
        'user': current_user,
        'character': chosen_character,
        'form': form,
        'skills': character_skills
    }
    return render(request, "character_add_skills.html", context)

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"