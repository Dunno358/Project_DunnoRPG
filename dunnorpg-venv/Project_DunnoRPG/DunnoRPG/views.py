from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.contrib import messages
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
            usedPoints = character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL

            if usedPoints <= limit:
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
                
                character.points_left = limit-usedPoints
                character.fullHP = character.HP
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
    character_stats = list(models.Character.objects.all().filter(owner=current_user, id=id).values())[0]
    character_skills_queryset = list(models.Skills.objects.filter(owner=current_user,character=chosen_character).values())
    character_skills = []

    for data in character_skills_queryset:
        character_skills.append({'skill': data['skill'], 'level': data['level']})

    skills_count = 0
    skills_count_magical = 0
    current_skills = []
    for skill in character_skills:
        category = models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['category'].lower()
        cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])
        current_skills.append(skill['skill'])
        if category == 'magical':
            skills_count_magical += skill['level']*cost
        else:
            if category != 'free':
                skills_count += skill['level']*cost

    skills_points = character_stats['points_left']-skills_count
    magical_skills_points = character_stats['INT']-skills_count_magical
    
    if request.method == 'POST':
        form = CharacterSkillsForm(request.POST)
        if form.is_valid():
            character_skills = form.save(commit=False)
            validated_skill = models.Skills_Decs.objects.filter(name=character_skills.skill).values()[0]

            free_points = 0
            if validated_skill['name'] in current_skills: #if exists than delete existing one
                skill_level = int(models.Skills.objects.filter(skill=validated_skill['name']).values()[0]['level'])
                skill_cost = int(models.Skills_Decs.objects.filter(name=validated_skill['name']).values()[0]['cost'])
                free_points = skill_level*skill_cost
                models.Skills.objects.filter(skill=validated_skill['name']).delete()

            if validated_skill['category'].lower() == 'magical':
                correct = magical_skills_points>0 and character_skills.level <= magical_skills_points+free_points
            else:
                correct = skills_points>0 and character_skills.level <= skills_points+free_points

            print(character_skills.level)

            if correct:
                character_skills.owner = current_user
                character_skills.save()

                skill = models.Skills.objects.last()
                skill_desc = models.Skills_Decs.objects.filter(name=skill.skill).values()[0]['desc']
                skill_category = models.Skills_Decs.objects.filter(name=skill.skill).values()[0]['category']

                skill.character = chosen_character
                skill.desc = skill_desc
                skill.category = skill_category
                skill.save()
                return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{id}')
            else:
                return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{id}')
    else:
        form = CharacterSkillsForm()

    context = {
        'user': current_user,
        'character': chosen_character,
        'form': form,
        'skills': character_skills,
        'skills_count': skills_points,
        'skills_count_magical': magical_skills_points
    }
    return render(request, "character_add_skills.html", context)

def skills(request):
    magical_skills = list(models.Skills_Decs.objects.all().filter(category='Magical').values())
    melee_skills = list(models.Skills_Decs.objects.all().filter(category='Melee').values())
    range_skills = list(models.Skills_Decs.objects.all().filter(category='Range').values())
    agility_skills = list(models.Skills_Decs.objects.all().filter(category='Agility').values())
    education_skills = list(models.Skills_Decs.objects.all().filter(category='Education').values())
    animals_skills = list(models.Skills_Decs.objects.all().filter(category='Animals').values())
    eq_skills = list(models.Skills_Decs.objects.all().filter(category='Equipment').values())
    crafting_skills = list(models.Skills_Decs.objects.all().filter(category='Crafting').values())
    drinking_skills = list(models.Skills_Decs.objects.all().filter(category='Drinking').values())
    charisma_skills = list(models.Skills_Decs.objects.all().filter(category='Charisma').values())
    command_skills = list(models.Skills_Decs.objects.all().filter(category='Command').values())
    horsemanship_skills = list(models.Skills_Decs.objects.all().filter(category='Horsemanship').values())
    aliigment_skills = list(models.Skills_Decs.objects.all().filter(category='Alligment').values())

    other_skills = drinking_skills+charisma_skills+command_skills+horsemanship_skills+aliigment_skills
    current_user = request.user
    
    context = {
        'magical_skills': magical_skills,
        'melee_skills': melee_skills,
        'range_skills': range_skills,
        'agility_skills': agility_skills,
        'education_skills': education_skills,
        'animals_skills': animals_skills,
        'eq_skills': eq_skills,
        'other_skills': other_skills,
        'skills': ['Magical','Melee','Range','Agility','Education','Animals','Equipment','Other'],
        'user': current_user
    }
    return render(request, "skills.html", context)

def skill_detail(request, id):
    current_user = request.user
    chosen = models.Skills_Decs.objects.all().filter(id=id).values()[0]
    levels = []
    for info in chosen:
        if info.startswith('level') and len(chosen[info])>0:
            levels.append({'level': info, 'desc': chosen[info]})

    context = {
        'skill': chosen,
        'levels': levels,
        'user': current_user
    }

    return render(request, 'skill_detail.html', context)

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"