from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.views.generic import FormView
from django.contrib import messages
from django.shortcuts import redirect
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
from DunnoRPG.serializers import ItemSerializer
from DunnoRPG.serializers import CharacterSerializer
from DunnoRPG.serializers import SkillsSerializer
from . import models
from .forms import CharacterForm
from .forms import CharacterSkillsForm

class charGET(APIView):
    serializer_class = CharacterSerializer
    template_name = 'home.html'
    renderer_classes = [TemplateHTMLRenderer]

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
                models.Skills.objects.create(owner=current_user,character=character.name,skill=skill[1:],category=f'{skill[0]}free',level=skill[0])

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

class Skills(APIView):
    serializer_class = SkillsSerializer
    template_name = 'character_add_skills.html'
    form_class = CharacterSkillsForm
    renderer_classes = [TemplateHTMLRenderer]

    def get(self,request,id):
        current_user = request.user
        chosen_character = models.Character.objects.filter(owner=current_user, id=id).values()[0]['name']
        character_skills_queryset = models.Skills.objects.all().filter(owner=current_user,character=chosen_character).values()
        serializer = SkillsSerializer(character_skills_queryset,many=True)        
        skills_count = 0
        skills_count_magical = 0
        current_skills = []
        character_skills = []

        for data in character_skills_queryset:
            character_skills.append({'id': data['id'], 'skill': data['skill'], 'level': data['level'], 'category': data['category']})

        for skill in character_skills:
            category = models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['category'].lower()
            cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])       
            current_skills.append(skill['skill'])    
            if skill['category'] == 'magical':
                skills_count_magical += skill['level']*cost
            else:
                if skill['category'][1:] != 'free':
                    skills_count += skill['level']*cost

        character_stats = models.Character.objects.filter(owner=current_user, id=id).values()[0]
        skills_points = character_stats['points_left']
        magical_skills_points = character_stats['INT'] - skills_count_magical
        context = {
            'user': current_user,
            'character': chosen_character,
            'character_id': id,
            'character_stats': character_stats,
            'skills': character_skills,
            'skills_count': skills_points,
            'skills_count_magical': magical_skills_points,
            'form': CharacterSkillsForm()
        }
        return Response(context) 
    def post(self,request,id):
        current_user = request.user
        chosen_character = models.Character.objects.filter(owner=current_user, id=id).values()[0]
        character_skills_queryset = models.Skills.objects.filter(owner=current_user, character=chosen_character['name']).values()
        character_skills = []

        for data in character_skills_queryset:
            character_skills.append({
                'id': data['id'], 
                'skill': data['skill'], 
                'level': data['level'], 
                'category': data['category']
            })

        skills_count = 0
        skills_count_magical = 0
        current_skills = []

        for skill in character_skills:
            cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])
            current_skills.append(skill['skill'])
            if skill['category'].lower() == 'magical':
                skills_count_magical += skill['level']*cost
            elif skill['category'][1:] != 'free':
                skills_count += skill['level']*cost

        skills_points = chosen_character['points_left']-skills_count
        magical_skills_points = chosen_character['INT'] - skills_count_magical

        form = CharacterSkillsForm(request.POST)
        if form.is_valid():
            skill_to_add = form.save(commit=False)
            validated_skill = models.Skills_Decs.objects.filter(name=skill_to_add.skill).values()[0]

            requirements_satisfied = [True,True]
            req_stats = []
            for x in range(2):
                try:
                    req_stat = validated_skill[f"need{skill_to_add.level}_{x+1}"][:3]
                    req_value = int(validated_skill[f"need{skill_to_add.level}_{x+1}"][3])
                    req_stats.append(f"{req_stat}: {req_value}")
                    req_satisfied = chosen_character[req_stat] >= req_value
                    requirements_satisfied[x] = req_satisfied
                except:
                    pass
            
            requirements_satisfied = requirements_satisfied[0] and requirements_satisfied[1]
            if validated_skill['category'].lower()=='magical':
                avaible_points = magical_skills_points
            else:
                avaible_points = skills_points

            correct = False
            if avaible_points > 0 and skill_to_add.level <= avaible_points:
                if req_satisfied:
                    if validated_skill['name'] not in current_skills:
                        correct = True
                    else:
                        msg = f"{validated_skill['name']} is your skill already. Delete current one if you want to update."
                else:
                    msg = f"Requirements: "
                    for stat in req_stats:
                        msg += f"{stat}, "
                    msg = msg[:-2]
            else:
                msg = f"Not enough points: {avaible_points} points available and {skill_to_add.level} points are needed for {validated_skill['name']} lvl.{skill_to_add.level}"

            if correct:
                skill_details = models.Skills_Decs.objects.filter(name=skill_to_add.skill).values()[0]
                character = models.Character.objects.get(id=id)
                character.points_left -= skill_to_add.level*int(skill_details['cost'])
                character.save()
                skill_to_add.owner = current_user
                skill_to_add.character = chosen_character['name']
                skill_to_add.desc = skill_details['desc']
                skill_to_add.category = skill_details['category']
                skill_to_add.save()
            else:
                messages.error(request,msg)
        return HttpResponseRedirect(f'/dunnorpg/character_add_skills/{id}') 

def character_edit(request,id):
    chosen_character = list(models.Character.objects.all().filter(id=id).values())[0]
    print(chosen_character)

    context = {
        'character': chosen_character
    }
    return render(request, "character_edit.html", context)    

def skills(request):
    skills = models.Skills_Decs.objects.all()
    magical_skills = list(skills.filter(category='Magical').values())
    melee_skills = list(skills.filter(category='Melee').values())
    range_skills = list(skills.filter(category='Range').values())
    agility_skills = list(skills.filter(category='Agility').values())
    education_skills = list(skills.filter(category='Education').values())
    animals_skills = list(skills.filter(category='Animals').values())
    eq_skills = list(skills.filter(category='Equipment').values())
    crafting_skills = list(skills.filter(category='Crafting').values())
    drinking_skills = list(skills.filter(category='Drinking').values())
    charisma_skills = list(skills.filter(category='Charisma').values())
    command_skills = list(skills.filter(category='Command').values())
    horsemanship_skills = list(skills.filter(category='Horsemanship').values())
    aliigment_skills = list(skills.filter(category='Alligment').values())

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
    skill = models.Skills.objects.filter(id=skill_id)
    skill_details = models.Skills_Decs.objects.filter(name = skill.values()[0]['skill']).values()[0]
    character = models.Character.objects.filter(id=char_id).get()
    character.points_left += skill.values()[0]['level']*int(skill_details['cost'])
    character.save()
    skill.delete()
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"