from django.shortcuts import render
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.views.generic import FormView
from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import generics
from rest_framework.reverse import reverse
from rest_framework.permissions import AllowAny, IsAuthenticated
from DunnoRPG.serializers import ItemSerializer
from DunnoRPG.serializers import CharacterSerializer
from . import models
from .forms import CharacterForm
from .forms import CharacterSkillsForm

import requests

class charGET(APIView):
    serializer_class = CharacterSerializer
    template_name = 'home.html'
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [AllowAny]

    def get(self, request):
        avaible_characters = models.Character.objects.all().filter(owner=self.request.user)
        serializer = self.serializer_class(avaible_characters, many=True)
        serialized_data = serializer.data
        context = {
            'characters': serialized_data,
            'characters_count': len(serialized_data)            
        }
        return Response(context, template_name=self.template_name)
    
class charPOST(FormView):
    template_name = 'character_add.html'
    form_class = CharacterForm
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        character = form.save(commit=False)
        current_user = self.request.user

        character.owner = current_user
        chosen_race = models.Races.objects.all().filter(name=character.race).values()[0]
        usedPoints = character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL
        
        valid = False
        if usedPoints <= chosen_race['points_limit']:
            valid = True

        if valid:
            character.size = chosen_race['size']

            character.points_left = chosen_race['points_limit'] - (character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL)

            pluses = chosen_race['statPlus'].split(';')
            minuses = chosen_race['statMinus'].split(';')
            character.INT += int(pluses[0])-int(minuses[0])
            character.SIŁ += int(pluses[1])-int(minuses[1])
            character.ZRE += int(pluses[2])-int(minuses[2])
            character.CHAR += int(pluses[3])-int(minuses[3])
            character.CEL += int(pluses[4])-int(minuses[4])

            character.fullHP = character.HP

            for skill in chosen_race['Skills'].split(';'):
                models.Skills.objects.create(owner=current_user,character=character.name,skill=skill[1:],category='free',level=skill[0])

            character.save()

            return redirect(f'character_add_skills/{character.id}')
        else:
            messages.warning(self.request,'Not enought points.')
            return redirect(f'character_add')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

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
    print(character_skills_queryset)
    character_skills = []
    msg = ''

    for data in character_skills_queryset:
        character_skills.append({'id': data['id'], 'skill': data['skill'], 'level': data['level'], 'category': data['category']})

    skills_count = 0
    skills_count_magical = 0
    current_skills = []
    for skill in character_skills:
        category = models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['category'].lower()
        cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])
        current_skills.append(skill['skill'])
        if skill['category'] == 'magical':
            skills_count_magical += skill['level']*cost
        else:
            if skill['category'] != 'free':
                skills_count += skill['level']*cost

    skills_points = character_stats['points_left']-skills_count
    magical_skills_points = character_stats['INT']-skills_count_magical
    
    if request.method == 'POST':
        form = CharacterSkillsForm(request.POST)
        if form.is_valid():
            character_skills = form.save(commit=False)
            validated_skill = models.Skills_Decs.objects.filter(name=character_skills.skill).values()[0]

            requirements_satisfied = [True,True] #Checking stats requirements for skill chosen lvl
            req_stats = []
            if validated_skill['category'] != 'Magical':
                for x in range(2):
                    try:
                        req_stat = validated_skill[f"need{character_skills.level}_{x+1}"][:3]
                        req_value = int(validated_skill[f"need{character_skills.level}_{x+1}"][3])
                        req_stats.append(f"{req_stat}: {req_value}")
                        req_satisfied = character_stats[req_stat] >= req_value
                        requirements_satisfied[x] = req_satisfied
                    except:
                        pass
            requirements_satisfied = requirements_satisfied[0] and requirements_satisfied[1]

            if validated_skill['category'].lower() == 'magical':
                category_points = magical_skills_points
            else:
                category_points = skills_points

            if category_points>0 and character_skills.level <= category_points:
                if requirements_satisfied:
                    if validated_skill['name'] not in current_skills:
                        correct = True
                    else:
                        msg = f"{validated_skill['name']} is your skill already. Delete current one if you want to update."
                        correct = False
                else:
                    msg = f"Requirements: "
                    for stat in req_stats:
                        msg += f"{stat}, "
                    msg = msg[:-2]
                    correct = False
            else:
                msg = f"Not enough points: {category_points} points avaible and {character_skills.level} points are needed for {validated_skill['name']} lvl.{character_skills.level}"
                correct = False


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
                messages.error(request, msg)
                return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{id}')
    else:
        form = CharacterSkillsForm()

    context = {
        'user': current_user,
        'character': chosen_character,
        'character_id': character_stats['id'],
        'character_stats': character_stats,
        'form': form,
        'skills': character_skills,
        'skills_count': skills_points,
        'skills_count_magical': magical_skills_points
    }
    return render(request, "character_add_skills.html", context)

def character_edit(request,id):
    chosen_character = list(models.Character.objects.all().filter(id=id).values())[0]
    print(chosen_character)

    context = {
        'character': chosen_character
    }
    return render(request, "character_edit.html", context)    

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
            try:
                need_info1 = chosen[f"need{info[5]}_1"]
                need1 = f"{need_info1[:3]}: {need_info1[3]}"
            except:
                need1  =''
            try:
                need_info2 = chosen[f"need{info[5]}_2"]
                need2 = f"{need_info2[:3]}: {need_info2[3]}"
            except:
                need2=''
            levels.append({'level': info, 'desc': chosen[info], 'need1': need1, 'need2': need2})
    print(levels)

    context = {
        'skill': chosen,
        'levels': levels,
        'user': current_user
    }

    return render(request, 'skill_detail.html', context)

def skill_delete(request,char_id,skill_id):
    skill = models.Skills.objects.filter(id=skill_id).delete()
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')

class rest_test(generics.ListCreateAPIView):
    queryset = models.Items.objects.all()
    serializer_class = ItemSerializer

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"