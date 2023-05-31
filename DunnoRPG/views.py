from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.views.generic.edit import CreateView
from DunnoRPG.serializers import (CharacterSerializer, ItemSerializer, SkillsDecsSerializer, SkillsSerializer)
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.generic.detail import DetailView
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from . import models
from .forms import CharacterForm, CharacterSkillsForm

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
        return Response(context)
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
                
            character.weaponBonus = chosen_race['weaponsBonus']
            character.preferredWeapons = chosen_race['weaponsPreffered']
            character.unlikedWeapons = chosen_race['weaponsUnliked']

            character.save()

            skills = models.Skills.objects
            for skill in chosen_race['Skills'].split(';'):
                skill_name = skill[1:].strip()
                skill_level = skill[0]
                skills.create(
                    owner=current_user,
                    character=character.name,
                    skill=skill_name,
                    category=f'{skill_level}free',
                    level=skill_level,
                    desc = models.Skills_Decs.objects.all().filter(name=skill_name).values()[0]['desc']
                    )

            return redirect(f'character_add_skills/{character.id}')
        else:
            messages.error(self.request,'Not enought points.')
            return redirect(f'character_add')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class CharacterSkills(APIView):
    serializer_class = SkillsSerializer
    template_name = 'character_add_skills.html'
    form_class = CharacterSkillsForm
    renderer_classes = [TemplateHTMLRenderer]

    def get(self,request,id):
        current_user = request.user
        chosen_character = models.Character.objects.filter(owner=current_user, id=id).values()[0]['name']
        character_skills_queryset = models.Skills.objects.all().filter(owner=current_user,character=chosen_character).values()
        skills_count = 0
        skills_count_magical = 0
        current_skills = []
        character_skills = []

        for data in character_skills_queryset:
            character_skills.append({'id': data['id'], 'skill': data['skill'], 'level': data['level'], 'category': data['category']})

        for skill in character_skills:
            cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])       
            current_skills.append(skill['skill'])    
            if skill['category'].lower() == 'magical':
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

        skills_points = chosen_character['points_left']
        magical_skills_points = chosen_character['INT'] - skills_count_magical
        if magical_skills_points<0:
            magical_skills_points = 0

        form = CharacterSkillsForm(request.POST)
        if form.is_valid():
            skill_to_add = form.save(commit=False)
            validated_skill = models.Skills_Decs.objects.filter(name=skill_to_add.skill).values()[0]

            level = skill_to_add.level
            while True:
                level_desc = validated_skill[f"level{level}"]
                if len(level_desc)>0:
                    skill_to_add.level = level
                    break
                else:
                    level -= 1
                    continue
                    
            requirements_satisfied = [True,True]
            req_stats = []
            for x in range(2):
                try:
                    req_stat = validated_skill[f"need{skill_to_add.level}_{x+1}"][:3]
                    req_value = int(validated_skill[f"need{skill_to_add.level}_{x+1}"][3])
                    if req_stat == 'CHA':
                        req_stat = 'CHAR'
                    req_stats.append(f"{req_stat}: {req_value}")
                    req_satisfied = chosen_character[req_stat] >= req_value
                    requirements_satisfied[x] = req_satisfied
                except:
                    req_satisfied = True
            
            requirements_satisfied = requirements_satisfied[0] and requirements_satisfied[1]
            if validated_skill['category'].lower()=='magical':
                avaible_points = magical_skills_points
            else:
                avaible_points = skills_points

            correct = False
            if avaible_points > 0 and skill_to_add.level <= avaible_points:
                if requirements_satisfied:
                    if validated_skill['name'] not in current_skills:
                        correct = True
                    else:
                        msg = f"{validated_skill['name']} is your skill already."
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
                if validated_skill['category'].lower() != 'magical':
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

class CharacterDetails(APIView):
    serializer_class = CharacterSerializer
    template_name = 'character_detail.html'
    renderer_classes = [TemplateHTMLRenderer]

    def get(self,request,id):
        chosen = models.Character.objects.all().filter(id=id).values()
        serializer = CharacterSerializer(chosen, many=True)

        skills = models.Skills.objects.all().filter(owner=request.user,character=chosen[0]['name']).values()
        race = models.Races.objects.all().filter(name=serializer.data[0]['race']).values()[0]
        mods = models.Mods.objects.all().filter(owner=request.user,character=serializer.data[0]['name']).values()

        for index in range(len(skills)):
            skill = skills[index]
            skill_description = models.Skills_Decs.objects.all().filter(name=skills[index]['skill']).values()[0]
            skill['original_id'] = skill_description['id']
            skill['original_desc'] = skill_description['desc']
            skill['level_desc'] = skill_description[f"level{skill['level']}"]

        context = {
            'chosen_character': serializer.data,
            'mods': mods,
            'skills': skills,
            'race_desc': race['desc'],
            'mods': mods
        }
        return Response(context)  

class UpgradeCharacterStats(APIView):
    def get(self, request, *args, **kwargs):
        char_id = kwargs['char_id']
        stat = kwargs['stat']
        
        character = get_object_or_404(models.Character, id=char_id)
        if int(character.points_left)>0:
            setattr(character, stat, int(getattr(character, stat))+1)
                
            character.points_left -= 1
            character.save()
        else:
            messages.error(request, 'Not enough points.')
        
        return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
    
class DowngradeCharacterStats(APIView):
    def get(self, request, *args, **kwargs):
        char_id = kwargs['char_id']
        stat = kwargs['stat']
        
        character = get_object_or_404(models.Character, id=char_id)
        stat_val = getattr(character,stat)
        
        if stat_val>0:
            #if int also check if magical_skills>0
            setattr(character,stat,stat_val-1)
        else:
            messages.error(request, 'Stat cannot be lower than 0.')
            return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
                
        character.points_left += 1
        character.save()
        
        return redirect(f'/dunnorpg/character_add_skills/{char_id}/')

class Skills(APIView):
    serializer_class = SkillsDecsSerializer
    template_name = 'skills.html'
    rendered_classes = [TemplateHTMLRenderer]

    def get(self,request):
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
        current_user = request.user

        other_skills = drinking_skills+charisma_skills+command_skills+horsemanship_skills+aliigment_skills+crafting_skills
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
        return Response(context)

class SkillDetail(APIView):
    serializer_class = SkillsDecsSerializer
    template_name = 'skill_detail.html'
    rendered_classes = [TemplateHTMLRenderer]

    def get(self,request,id):
        current_user = request.user
        serializer = SkillsDecsSerializer(models.Skills_Decs.objects.all().filter(id=id).values()[0])
        levels = []

        for data in serializer.data:
            if data.startswith('level') and len(serializer.data[data])>0:
                try:
                    need1_label = serializer.data[f"need{data[5]}_1"]
                    need1 = f"{need1_label[:3]}: {need1_label[3]}"
                except:
                    need1 = ''
                try:
                    need2_label = serializer.data[f"need{data[5]}_2"]
                    need2 = f"{need2_label[:3]}: {need2_label[3]}"
                except:
                    need2 = ''
                levels.append({'level': data, 'desc': serializer.data[data], 'need1': need1, 'need2': need2})

        context = {
            'skill': serializer.data,
            'levels': levels,
            'user': current_user
        }

        return Response(context)

def skill_delete(request,char_id,skill_id):
    skill = get_object_or_404(models.Skills, id=skill_id)
    skill_details = get_object_or_404(models.Skills_Decs, name=skill.skill)
    character = get_object_or_404(models.Character, id=char_id)
    
    if skill.category != 'Magical':
        character.points_left += skill.level*int(skill_details.cost)
        character.save()
    skill.delete()
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
def skill_upgrade(request,char_id,skill_id):
    skill = get_object_or_404(models.Skills, id=skill_id)
    skill_details = models.Skills_Decs.objects.filter(name=skill.skill).values()[0]
    character = models.Character.objects.filter(id=char_id).values()[0]
    character_object = get_object_or_404(models.Character, id=char_id)
    try:
        not_max_lvl = len(skill_details[f"level{skill.level+1}"])>0
    except:
        not_max_lvl = False
    
    if not_max_lvl:
        need1 = skill_details[f"need{skill.level+1}_1"]
        need2 = skill_details[f"need{skill.level+1}_2"]
        req1_OK = (need1==None) or ( int(character[f"{need1[:3]}"])>int(need1[3]) )
        req2_OK = (need2==None) or ( int(character[f"{need2[:3]}"])>int(need2[3]) )

        if req1_OK and req2_OK:
            cat = skill_details['category']
            points_ok = True
            if cat=='Magical':
                mag_points = 0
                magical_skills = models.Skills.objects.filter(character=character['name'], category='Magical').values()
                
                for mag_skill in magical_skills:
                    detailed_info = get_object_or_404(models.Skills_Decs, name=mag_skill['skill'])
                    mag_points += int(mag_skill['level'])*int(detailed_info.cost)
                
                if int(character['INT'])-mag_points <= 0:
                    points_ok = False
               
            if points_ok:        
                skill.level += 1
                skill.desc = skill_details['desc']+' '+skill_details[f"level{skill.level}"]
                skill.save()

                character_object.points_left -= int(skill_details['cost'])
                character_object.save()
            else:
                messages.error(request, f'Not enough points to upgrade {skill.skill}.')
        else:
            msg = f"Your stats are too low to upgrade {skill.skill}, you need "
            if need1!=None:
                msg += f"{need1[:3]}({need1[3]})"
                if need2 != None:
                    msg += f" and {need2[:3]}({need2[3]})."
            elif need2!=None:
                msg += f"{need2[:3]}({need2[3]})."
            messages.error(request, msg)
    else:
        messages.error(request,f'{skill.skill} maximum level reached!')
    
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
def skill_downgrade(request,char_id,skill_id):
    skill = get_object_or_404(models.Skills, id=skill_id)
    skill_details = models.Skills_Decs.objects.filter(name=skill.skill).values()[0]
    character = models.Character.objects.filter(id=char_id).values()[0]
    character_object = get_object_or_404(models.Character, id=char_id)
    
    try:
        not_min_lvl = len(skill_details[f"level{skill.level-1}"])>0
    except:
        not_min_lvl = False   
        
    if not_min_lvl:
        skill.level -= 1
        skill.desc = skill_details['desc']+' '+skill_details[f"level{skill.level}"]
        skill.save()
        
        character_object.points_left += int(skill_details['cost'])
        character_object.save()
    else:
        messages.error(request,f'{skill.skill} level cannot be lower!')
    
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')

def log_as_guest(request):
    guest_user = User.objects.get(username='Guest')
    user = authenticate(request, username='Guest', password='GuestPassword')
    if user is not None:
        login(request, user)
        return redirect('home')
    else:
        return HttpResponse('Invalid login')

class GMPanel(APIView):
    template_name = 'gm_panel.html'
    renderer_classes = [TemplateHTMLRenderer]
    def get(self,request):
        
        context = {
            
        }
        
        return Response(context)
    
class Info(APIView):
    template_name = 'info.html'
    renderer_classes = [TemplateHTMLRenderer]
    def get(self,request):
        
        context = {
            
        }
        
        return Response(context)
    
class AccRules(APIView):
    template_name = 'acc-rules.html'
    renderer_classes = [TemplateHTMLRenderer]
    def get(self,request):
        
        context = {
            
        }
        
        return Response(context)

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"