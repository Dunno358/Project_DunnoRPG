from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.apps import apps
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.decorators import user_passes_test
import traceback
import json
import math

from DunnoRPG.serializers import (CharacterSerializer, ItemSerializer,
                                  SkillsDecsSerializer, SkillsSerializer)

from . import models
from .forms import CharacterForm, CharacterSkillsForm, AddEqItemForm, AddEffectForm


class charGET(ListView):
    model = models.Character
    template_name = 'home.html'
    context_object_name = 'characters'
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.model.objects.all()
        else:
            return self.model.objects.filter(owner=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['characters_count'] = self.get_queryset().count()
        return context
    
class charPOST(FormView):
    template_name = 'character_add.html'
    form_class = CharacterForm
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        character = form.save(commit=False)
        current_user = self.request.user

        character.owner = current_user
        chosen_race = get_object_or_404(models.Races, name=character.race)
        usedPoints = character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL
        
        valid = False
        if usedPoints <= chosen_race.points_limit:
            valid = True

        if valid:
            character.size = chosen_race.size

            try:
                char_class = get_object_or_404(models.Classes, name=character.chosen_class)
                class_skills = char_class.skills.split(";")
                while "" in class_skills:
                    class_skills.remove("")

                class_effects = char_class.effects.split(";")
                while "" in class_effects:
                    class_effects.remove("")

                class_mods = char_class.mods.split(";")
                while "" in class_mods:
                    class_mods.remove("")

                class_hp_mod = char_class.hp_mod
                if class_hp_mod == "":
                    class_hp_mod = 0
                else:
                    class_hp_mod = int(class_hp_mod)
            except:
                class_hp_mod = 0
                class_skills = class_mods = class_effects = []

            character.points_left = chosen_race.points_limit - (character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL)

            pluses = chosen_race.statPlus.split(';')
            minuses = chosen_race.statMinus.split(';')
            character.INT += int(pluses[0])-int(minuses[0])
            character.SIŁ += int(pluses[1])-int(minuses[1])
            character.ZRE += int(pluses[2])-int(minuses[2])
            character.CHAR += int(pluses[3])-int(minuses[3])
            character.CEL += int(pluses[4])-int(minuses[4])

            character.fullHP = character.HP = character.HP+class_hp_mod
                
            character.weaponBonus = chosen_race.weaponsBonus
            character.preferredWeapons = chosen_race.weaponsPreffered
            character.unlikedWeapons = chosen_race.weaponsUnliked

            character.save()

            skills = models.Skills.objects
            race_skills = chosen_race.Skills.split(';')
            for skill in race_skills:
                try:
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
                except:
                    print(f"Skipped {skill} because of {traceback.format_exc()}")
            for skill in class_skills: #second loop as class skills are defined little different
                try:
                    skill_name = skill[:-1].strip()
                    skill_level = skill[-1]
                    if not f"{skill_level}{skill_name}" in race_skills:
                        skills.create(
                            owner=current_user,
                            character=character.name,
                            skill=skill_name,
                            category=f'{skill_level}free',
                            level=skill_level,
                            desc = models.Skills_Decs.objects.all().filter(name=skill_name).values()[0]['desc']
                            )
                except:
                    print(f"Skipped {skill} because of {traceback.format_exc()}")

            effects = models.Effects.objects
            for effect in class_effects:
                name = effect.split("-")[0]
                bonus = effect.split("-")[1]
                if bonus.lower().endswith("m"):
                    bonus = -int(bonus[:-1])
                else:
                    bonus = int(bonus)
                effects.create(
                    owner=current_user,
                    character=character.name,
                    name = name,
                    bonus = bonus,
                    time = 110               
                )

            mods = models.Mods.objects
            for mod in class_mods:
                if "+" in mod:
                    name = mod.split("+")[0]
                    bonus = int(mod.split("+")[1])
                elif "-" in mod:
                    name = mod.split("-")[0]
                    bonus = -int(mod.split("-")[1])   
                mods.create(
                    owner=current_user,
                    character=character.name,
                    field = name,
                    value = bonus,                   
                )                 

            return redirect(f'character_add_skills/{character.id}')
        else:
            messages.error(self.request,'Not enought points.')
            return redirect(f'character_add')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class DeleteCharacter(APIView):
    def get(self,request,char_id):
        character = get_object_or_404(models.Character,id=char_id)
        
        with transaction.atomic():
            models.Skills.objects.filter(owner=request.user ,character=character.name).delete()
            models.Effects.objects.filter(owner=request.user ,character=character.name).delete()
            character.delete()

        return redirect('/dunnorpg')

class CharacterSkills(ListView, FormView):
    model = models.Skills
    template_name = 'character_add_skills.html'
    context_object_name = 'skills'
    form_class = CharacterSkillsForm
    
    def get_queryset(self):
        user = self.request.user
        id = self.kwargs['id']
        chosen_character = get_object_or_404(models.Character, id=id)
        character_skills_queryset = models.Skills.objects.all().filter(owner=chosen_character.owner, character=chosen_character.name).values() 
        
        return character_skills_queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        id = self.kwargs['id']
        chosen_character = get_object_or_404(models.Character, id=id).name
        character_stats = models.Character.objects.filter(id=id).values()[0]
        skills_points = character_stats['points_left']
        skills_count_magical = 0
        current_skills = []

        for skill in context['skills']:
            cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])
            current_skills.append(skill['skill'])
            if skill['category'].lower() == 'magical':
                skills_count_magical += skill['level'] * cost

        magical_skills_points = character_stats['INT'] - skills_count_magical
        if magical_skills_points < 0:
            magical_skills_points = 0

        users = []
        for user in User.objects.values():
            users.append(user)

        context['character'] = chosen_character
        context['character_id'] = id
        context['character_stats'] = character_stats
        context['skills_count'] = skills_points
        context['skills_count_magical'] = magical_skills_points
        context['form'] = CharacterSkillsForm()
        context['users'] = users

        return context            
    def form_valid(self, form):
        id = self.kwargs['id']
        chosen_character = models.Character.objects.filter(id=id).values()[0]
        character_skills_queryset = models.Skills.objects.filter(owner=chosen_character['owner'], character=chosen_character['name']).values()
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
                skills_count_magical += skill['level'] * cost
            elif skill['category'][1:] != 'free':
                skills_count += skill['level'] * cost
                
        skills_points = chosen_character['points_left']
        magical_skills_points = chosen_character['INT'] - skills_count_magical
        if magical_skills_points < 0:
            magical_skills_points = 0

        skill_to_add = form.save(commit=False)
        validated_skill = models.Skills_Decs.objects.filter(name=skill_to_add.skill).values()[0]

        level = skill_to_add.level
        while True:
            level_desc = validated_skill[f"level{level}"]
            if len(level_desc) > 0:
                skill_to_add.level = level
                break
            else:
                level -= 1
                continue

        requirements_satisfied = [True, True]
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
        if validated_skill['category'].lower() == 'magical':
            available_points = magical_skills_points
        else:
            available_points = skills_points

        correct = False
        if available_points > 0 and skill_to_add.level <= available_points:
            if requirements_satisfied:
                if validated_skill['name'] not in current_skills:
                    correct = True
                else:
                    msg = f"{validated_skill['name']} is already one of your skills."
            else:
                msg = "Requirements: " + ", ".join(req_stats)
        else:
            msg = f"Not enough points: {available_points} points available and {skill_to_add.level} points are needed for {validated_skill['name']} lvl.{skill_to_add.level}"

        if correct:
            skill_details = models.Skills_Decs.objects.filter(name=skill_to_add.skill).values()[0]
            character = models.Character.objects.get(id=id)
            if validated_skill['category'].lower() != 'magical':
                character.points_left -= skill_to_add.level * int(skill_details['cost'])
            character.save()
            skill_to_add.owner = chosen_character['owner']
            skill_to_add.character = chosen_character['name']
            skill_to_add.desc = skill_details['desc']
            skill_to_add.category = skill_details['category']
            skill_to_add.save()
        else:
            messages.error(self.request, msg)

        return HttpResponseRedirect(self.get_success_url())
    def get_success_url(self):
        id = self.kwargs['id']
        return f'/dunnorpg/character_add_skills/{id}'

class CharacterDetails(DetailView):
    model = models.Character
    template_name = 'character_detail.html'

    def get_object(self,queryset=None):
        char_id = self.kwargs.get('id')
        character = get_object_or_404(models.Character, id=char_id)
        if character.owner != self.request.user.username and self.request.user.is_superuser == False:
            raise Http404('Invalid character')
        return character

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        chosen = self.get_object()
        serializer = CharacterSerializer(chosen)
        
        skills = models.Skills.objects.all().filter(owner=chosen.owner,character=serializer.data['name']).values()
        skillsMagical = []
        skillsMelee = []
        skillsRange = []
        skillsAgility = []
        skillsOther = []
        race = models.Races.objects.all().filter(name=serializer.data['race']).values()[0]
        mods = models.Mods.objects.all().filter(owner=chosen.owner,character=serializer.data['name']).values()

        try:
            chosen_class = get_object_or_404(models.Classes, name=chosen.chosen_class)
        except:
            chosen_class = {}

        for skill in skills:
            skill_description = models.Skills_Decs.objects.all().filter(name=skill['skill']).order_by('category').values()[0]
            skill['original_id'] = skill_description['id']
            skill['original_desc'] = skill_description['desc']
            skill['level_desc'] = skill_description[f"level{skill['level']}"]
            skill['max_uses'] = skill_description[f"useslvl{skill['level']}"]
            if skill_description['category'].lower() == 'magical': 
                skillsMagical.append(skill)
            elif skill_description['category'].lower() == 'melee': 
                skillsMelee.append(skill)
            elif skill_description['category'].lower() == 'range': 
                skillsRange.append(skill)
            elif skill_description['category'].lower() == 'agility': 
                skillsAgility.append(skill)
            else: 
                skillsOther.append(skill)

        types = ['Helmet','Torso','Boots','Gloves','Amulet','Other']

        eq_helmets_qs = models.Eq.objects.filter(character=chosen.name, type='Helmet').order_by('name')
        eq_torsos_qs = models.Eq.objects.filter(character=chosen.name, type='Torso').order_by('name')
        eq_gloves_qs = models.Eq.objects.filter(character=chosen.name, type='Gloves').order_by('name')
        eq_boots_qs = models.Eq.objects.filter(character=chosen.name, type='Boots').order_by('name')
        eq_amulets_qs = models.Eq.objects.filter(character=chosen.name, type='Amulet').order_by('name')
        eq_mounts_qs = models.Eq.objects.filter(character=chosen.name, type='Animal').order_by('name')
        eq_mounts_armor_qs = models.Eq.objects.filter(character=chosen.name, type='Mount Armor').order_by('name')
        eq_weapons_qs = models.Eq.objects.filter(character=chosen.name).exclude(type__in=types).order_by('name')
        
        context['helmet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Helmet').first()
        context['torso'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Torso').first()
        context['gloves'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Gloves').first()
        context['boots'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Boots').first()
        context['amulet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Amulet').first()
        context['mount'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount').first()
        context['mount_armor'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_armor').first()
        context['leftItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Left').first()
        context['rightItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Right').first()
        context['sideItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Side').first()
        context['chosen_character'] = [serializer.data] 
        context['mods'] = mods
        context['skills'] = skills
        context['skillsMagical'] = skillsMagical
        context['skillsMelee'] = skillsMelee
        context['skillsRange'] = skillsRange
        context['skillsAgility'] = skillsAgility
        context['skillsOther'] = skillsOther
        context['race_desc'] = race['desc']
        context['race_id'] = race['id']

        context["class"] = chosen_class
        
        context['eq_weapons'] = eq_weapons_qs
        context['eq_helmets'] = eq_helmets_qs
        context['eq_torsos'] = eq_torsos_qs
        context['eq_gloves'] = eq_gloves_qs
        context['eq_boots'] = eq_boots_qs
        context['eq_amulets'] = eq_amulets_qs
        context['eq_mounts'] = eq_mounts_qs
        context['eq_mounts_armor'] = eq_mounts_armor_qs

        return context 
    
class MoveItemToEq(APIView):
    def get(self, request, *args, **kwargs):
        item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
        item_desc = get_object_or_404(models.Items, name=item.name)
        
        char = get_object_or_404(models.Character, name=item.character)
        
        eq_weight = 0
        eq = models.Eq.objects.filter(character=item.character)
        for obj in eq:
            eq_weight += obj.weight
            
        if item_desc.type == 'Animal':
            char.extra_capacity = 0
            char.save()
            
        if char.SIŁ > 0:
            max_weight = char.SIŁ*5+char.extra_capacity
        elif char.SIŁ < 0:
            max_weight = 3+(char.SIŁ*0.5)+char.extra_capacity
        else:
            max_weight = 3+char.extra_capacity           

        if eq_weight+item_desc.weight <= max_weight:
            if item_desc.type != "Mount Armor":
                models.Eq.objects.create(
                    owner = item.owner,
                    character = item.character,
                    name = item.name,
                    type = item_desc.type,
                    weight = item_desc.weight,
                    durability = item.durability
                )

            if item_desc.skillEffects != None:
                for effect in item_desc.skillEffects.split(';'):
                    effect = effect.split("-")
                    models.Effects.objects.filter(character=char.name, name=effect[0]).first().delete()

            item.delete()
        else:
            messages.error(request, f"Not enough space in {char.name}'s equipment for '{item.name}' ({eq_weight}/{max_weight}kg)")

        return redirect(f"/dunnorpg/character_detail/{kwargs['char_id']}")

class UpgradeCharacterStats(APIView):
    def get(self, request, *args, **kwargs):
        char_id = kwargs['char_id']
        stat = kwargs['stat']
        if stat not in {'INT', 'SIŁ', 'ZRE', 'CHAR', 'CEL'}:
            raise Http404('Invalid character statistic')
        
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
        if stat not in {'INT', 'SIŁ', 'ZRE', 'CHAR', 'CEL'}:
            raise Http404('Invalid character statistic')
        
        character = get_object_or_404(models.Character, id=char_id)
        stat_val = getattr(character,stat)
        
        if stat_val>0:
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

        magical_skills = list(skills.filter(category='Magical').values().order_by('name'))
        melee_skills = list(skills.filter(category='Melee').values().order_by('name'))
        range_skills = list(skills.filter(category='Range').values().order_by('name'))
        agility_skills = list(skills.filter(category='Agility').values().order_by('name'))
        education_skills = list(skills.filter(category='Education').values().order_by('name'))
        animals_skills = list(skills.filter(category='Animals').values().order_by('name'))
        eq_skills = list(skills.filter(category='Equipment').values().order_by('name'))
        crafting_skills = list(skills.filter(category='Crafting').values().order_by('name'))
        drinking_skills = list(skills.filter(category='Drinking').values().order_by('name'))
        charisma_skills = list(skills.filter(category='Charisma').values().order_by('name'))
        command_skills = list(skills.filter(category='Command').values().order_by('name'))
        horsemanship_skills = list(skills.filter(category='Horsemanship').values().order_by('name'))
        aliigment_skills = list(skills.filter(category='Alligment').values().order_by('name'))
        current_user = request.user

        for x in range(len(magical_skills)):
            magical_skills[x]["number"] = x+1

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
        skill_exist = get_object_or_404(models.Skills_Decs, id=id)
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
    character_object = get_object_or_404(models.Character, id=char_id)
    character = models.Character.objects.filter(id=char_id).values()[0]
    try:
        not_max_lvl = len(skill_details[f"level{skill.level+1}"])>0
    except:
        not_max_lvl = False
    
    if not_max_lvl:
        need1 = skill_details[f"need{skill.level+1}_1"]
        need2 = skill_details[f"need{skill.level+1}_2"]
        req1_OK = (need1==None) or ( int(character[f"{need1[:3]}"])>=int(need1[3]) )
        req2_OK = (need2==None) or ( int(character[f"{need2[:3]}"])>=int(need2[3]) )

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
            else:
                points_ok = character_object.points_left>0
               
            if points_ok:        
                skill.level += 1
                skill.desc = skill_details['desc']+' '+skill_details[f"level{skill.level}"]
                skill.save()

                if cat != 'Magical':
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
    character_object = get_object_or_404(models.Character, id=char_id)
    character = models.Character.objects.filter(id=char_id).values()[0]
    
    try:
        not_min_lvl = len(skill_details[f"level{skill.level-1}"])>0
    except:
        not_min_lvl = False   
        
    if not_min_lvl:
        skill.level -= 1
        skill.desc = skill_details['desc']+' '+skill_details[f"level{skill.level}"]
        skill.save()
        
        if skill_details['category'] != 'Magical':
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
def del_eq_item(request, **kwargs):
    itemDesc = get_object_or_404(models.Items, id=kwargs['obj_id'])
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    item = models.Eq.objects.filter(name=itemDesc.name, character=char.name).first()
    if item.amount == 1:
        item.delete()
    else:
        item.amount -= 1
        item.weight -= itemDesc.weight
        item.save()
    return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")
def sell_item(request, **kwargs):
    try:
        city = get_object_or_404(models.Cities, visiting=True)
        eqItem = get_object_or_404(models.Eq, id=kwargs['item_id'])
        itemDesc = get_object_or_404(models.Items, name=eqItem.name)
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        
        charisma = char.CHAR
        for mod in models.Mods.objects.filter(character=char.name, field="CHAR"):
            charisma += mod.value
        for item in models.CharItems.objects.filter(character=char.name):
            desc = get_object_or_404(models.Items, name=item.name)
            try:
                if "CHAR" in desc.skillStats:
                    for stat in desc.skillStats.split(";"):
                        if stat.startswith("CHAR"): charisma += int(f"{stat[4]}{stat[5]}")
            except:
                pass
        #print(f"charisma {charisma}")
        
        durability_percent = eqItem.durability/itemDesc.maxDurability
        #print(f"dur {durability_percent}")
        base_price = int(itemDesc.price*durability_percent*eqItem.amount)
        #print(f"totally base {itemDesc.price}")
        #print(f"base {base_price}")
        char_bonus = round(((charisma*4)*base_price)/100)
        #print(f"bonus {char_bonus}")
        price = int(base_price) + char_bonus #Get 100% of calculated price + [charisma*4]% bonus

        char.coins += price
        char.save()

        eqItem.delete()

        messages.success(request, f"Sprzedano {itemDesc.name} za {price} monet! Obecny majątek: {char.coins} monet.")
    except:
        messages.error(request, f"Gdzie chcesz to sprzedać? Najpierw zajrzyj z drużyną do jakiegoś miasta!")
    return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")
def give_item(request, **kwargs):
    from_char = get_object_or_404(models.Character, id=kwargs['from_char'])
    to_char = get_object_or_404(models.Character, id=kwargs['to_char'])
    given_amount = kwargs['amount']
    if kwargs["item_id"]!=0:
        eq_item = get_object_or_404(models.Eq, id=kwargs['item_id'])
        itemDesc = get_object_or_404(models.Items, name=eq_item.name)

        if given_amount <= eq_item.amount:
            if to_char.SIŁ > 0:
                max_weight = to_char.SIŁ*5+to_char.extra_capacity
            elif to_char.SIŁ <0:
                max_weight = 3+(to_char.SIŁ*0.5)+to_char.extra_capacity
            else:
                max_weight = 3+to_char.extra_capacity
                                                
            current_weight = 0
            for item in models.Eq.objects.filter(character=to_char.name):
                if "strzała" in item.name.lower():
                    try:
                        if models.CharItems.objects.filter(character=to_char.name, hand="Side").first().name=="Kolczan":
                            pass
                        else:
                            current_weight += item.weight 
                    except:
                        current_weight += item.weight 
                elif "pocisk" in item.name.lower():
                    try:
                        allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                        init_hands = [
                            models.CharItems.objects.filter(character=to_char.name, hand="Left").first(),
                            models.CharItems.objects.filter(character=to_char.name, hand="Right").first(),
                            models.CharItems.objects.filter(character=to_char.name, hand="Side").first()
                            ]
                        hands = []
                        for hand in init_hands:
                            try:
                                hands.append(hand.name)
                            except:
                                pass
                        canPassWeight = any(item in allowed_items for item in hands)
                        if canPassWeight:
                            pass
                        else:
                            current_weight += item.weight 
                    except:
                        print(traceback.format_exc())
                        current_weight += item.weight 
                else:
                    current_weight += item.weight 

            if itemDesc.weight * given_amount + current_weight <= max_weight:
                models.Eq.objects.create(
                    owner=to_char.owner,
                    character=to_char.name,
                    name=eq_item.name,
                    type=eq_item.type,
                    weight=eq_item.weight*given_amount,
                    durability=eq_item.durability,
                    amount=given_amount
                )

                messages.success(request, f"Transferred {eq_item.name} to {to_char.name}.")
                eq_item.delete()
            else:
                messages.error(request, f"Not enough space in {to_char.name} equipment.")
        else:
            messages.error(request, f"Chcesz dać więcej niż masz? Linióweczka...")
    else:
        if from_char.coins>=given_amount:
            from_char.coins -= given_amount
            from_char.save()
            to_char.coins += given_amount
            to_char.save()
            messages.success(request, f"Transferred {given_amount} coins to {to_char.name}.")
        else:
            messages.error(request, f"{from_char.name} is too poor for that.")
    return redirect(f"/dunnorpg/items/ch{from_char.id}")

def swap_side_to_hand(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    sideItem = get_object_or_404(models.CharItems, character=char.name, hand="Side")
    sideItemDesc = get_object_or_404(models.Items, name=sideItem.name)
    left = False

    if kwargs['hand'] == 'left':
        try:
            to_swap = get_object_or_404(models.CharItems, character=char.name, hand="Left")
        except:
            messages.error(request, "Nothing to swap with!")
            return redirect('character_detail', char.id)
        left = True
    else:
        try:
            to_swap = get_object_or_404(models.CharItems, character=char.name, hand="Right")
        except:
            messages.error(request, "Nothing to swap with!")
            return redirect('character_detail', char.id)

    to_swap_desc = get_object_or_404(models.Items, name=to_swap.name)
    to_swap.hand = "Side"

    try:
        rightItem = get_object_or_404(models.CharItems, hand="Right", character=char.name)
        rightItemDesc = get_object_or_404(models.Items, name=rightItem.name)
        right = True
    except:
        right = False

    if left:
        if sideItemDesc.dualHanded and right:
            rightItem = get_object_or_404(models.CharItems, hand="Right", character=char.name)
            rightItemDesc = get_object_or_404(models.Items, name=rightItem.name)

            models.Eq.objects.create(
                owner = char.owner,
                character = char.name,
                name = rightItem.name,
                type = rightItemDesc.type,
                weight = rightItemDesc.weight,
                durability = rightItem.durability,
                amount = 1
            )
            rightItem.delete()

        sideItem.hand = "Left"
        to_swap.save()
        sideItem.save()
    else:
        if not sideItemDesc.dualHanded:
            sideItem.hand="Right"
            to_swap.save()
            sideItem.save()
        else:
            messages.error(request, "Dual-handed weapons cannot be added to right hand!")

    return redirect('character_detail', char.id)
def change_item_durability(request,**kwargs):
    if request.method == 'POST':
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
        item.durability = int(request.POST['dur'])
        item.save()
        return redirect('character_detail', char.id)
def fix_item(request, **kwargs):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            char = get_object_or_404(models.Character, id=data['char_id'])
            item = get_object_or_404(models.CharItems, id=data['item_id'])
            item_desc = models.Items.objects.get(name=item.name)
            
            # Update item and character

            new_dur = item.durability + int(data['fix-dur'])
            if new_dur <= item_desc.maxDurability:
                item.durability = new_dur
            else:
                item.durability = item_desc.maxDurability
            cost = int(data['cost'])
            char.coins -= cost
            
            # Save changes to the database
            item.save()
            char.save()

            # Return a success response
            return JsonResponse({"message": "Item fixed successfully", "new_durability": item.durability, "cost": cost}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)
def change_coins(request, **kwargs):
    if request.method == 'POST':
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        if request.user.is_superuser:
            char.coins = request.POST['coins-amount']
            char.save()
        else:
            messages.error(request,"Only GM can change coins, go and ask your GM to do so.")
        return redirect('character_detail', char.id)  
def change_health(request, **kwargs):  
    if request.method == 'POST':
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        if request.user.is_superuser:
            char.HP = request.POST['hp']
            char.save()
        else:
            messages.error(request,"Only GM can change health, go and ask your GM to do so.")
        return redirect('character_detail', char.id) 
def char_wear_item(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    char_skills = models.Skills.objects.filter(character=char.name)
    place = kwargs['place'] #hand or position
    item_id = kwargs['item_id']
    item_eq_obj = models.Eq.objects.get(character=char.name,id=item_id)
    item = models.Items.objects.get(name=item_eq_obj.name)
    
    if item.type == 'Animal':
        char.extra_capacity = item.diceBonus
        char.save()
     
    wolverin_barbarian = 'barbarzyńca: droga rosomaka'
    paladin = 'paladyn: przysięga miecza'
    
    allowed_classes = [wolverin_barbarian, paladin]
                                
    if item.dualHanded==True and place != 'Side' and char.chosen_class.lower() not in allowed_classes:
        if place == 'Right':
            messages.error(request, 'Dual-Handed weapons can only be added to left hand!')
            return redirect('character_detail', char.id)
        elif models.CharItems.objects.filter(character=char.name, hand='Right').first() not in [None,'']:
            messages.error(request, 'Right hand must be empty for that!')
            return redirect('character_detail', char.id)
    else:
        if place == "Right" and char.chosen_class.lower() not in allowed_classes:
            leftItem = models.CharItems.objects.filter(character=char.name, hand="Left").first()
            leftItemDesc = get_object_or_404(models.Items, name=leftItem.name)
            if leftItemDesc.dualHanded:
                allowed_types = ["shield"]
                if item.type.lower() not in allowed_types:
                    messages.error(request, 'You can only add shield to this type of weapon!')
                    return redirect('character_detail', char.id)

        
            
    charItObj = models.CharItems.objects.filter(hand=place.capitalize(), character=char.name).first()  
    if charItObj == None: 
        if place.lower() in ['left','right','side']:
            models.CharItems.objects.create(
                owner = request.user,
                character = char.name,
                name = item.name,
                durability = item_eq_obj.durability,
                hand = place.capitalize(),
                position = ''
                )
        else:
            models.CharItems.objects.create(
                owner = request.user,
                character = char.name,
                name = item.name,
                durability = item_eq_obj.durability,
                hand = '',
                position = place.capitalize()
                )            
    else:
        charItObj.name = item.name
        charItObj.durability = item_eq_obj.durability
        charItObj.save()  

    if item.skillEffects != None:
        for effect in item.skillEffects.split(';'):
            effect = effect.split("-")

            curr_effect = models.Effects.objects.filter(character=char.name, name=effect[0]).first()

            if curr_effect == None:
                models.Effects.objects.create(
                    owner = char.owner,
                    character=char.name,
                    name = effect[0],
                    bonus = effect[1],
                    time = effect[2]
                )
            else:
                curr_effect.time = 100
                curr_effect.save()

    if item.type != "Mount Armor":
        item_eq_obj.delete()
    return redirect('character_detail', char.id)
def char_use_skill(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    skill = get_object_or_404(models.Skills, id=kwargs['skill_id'])

    if skill.uses_left != 0:
        skill.uses_left -= 1
        skill.save()
        messages.warning(request, f'Used {skill.skill}.')
    else:
        messages.error(request, f'No uses left for {skill.skill}.')
    return redirect('character_detail', char.id)
def reset_skills(request,mode):
    for skill in models.Skills.objects.all():
        try:
            skill_desc = models.Skills_Decs.objects.filter(name=skill.skill).values()
            skill_max_uses = skill_desc[0][f"useslvl{skill.level}"]
            if skill_max_uses != None:
                if (mode == 'normal' and skill.category.lower() != 'magical') or mode == 'all':
                    skill.uses_left = skill_max_uses
                    skill.save()
        except:
            print(f"Cannot reset for: {skill}")
    return redirect('gm_panel')

def update_field(request, **kwargs):
    text = request.POST.get('notes-text')
    field_id = request.POST.get('id')
    model = request.POST.get('model')
    
    if model == "Character":
        obj = get_object_or_404(models.Character, id=field_id)
        obj.notes = text
        obj.save()
    
    return redirect('character_detail', field_id)

def char_change_owner(request, **kwargs):
    new_owner = request.POST['new_owner']
    char = get_object_or_404(models.Character, id=request.POST['chosen_character_id'])
    
    for item in models.CharItems.objects.filter(owner=char.owner, character=char.name):
        item.owner = new_owner
        item.save()
    for effect in models.Effects.objects.filter(owner=char.owner, character=char.name):
        effect.owner = new_owner
        effect.save()    
    for eq in models.Eq.objects.filter(owner=char.owner, character=char.name):
        eq.owner = new_owner
        eq.save()  
    for mod in models.Mods.objects.filter(owner=char.owner, character=char.name):
        mod.owner = new_owner
        mod.save() 
    for skill in models.Skills.objects.filter(owner=char.owner, character=char.name):
        skill.owner = new_owner
        skill.save() 
    
    char.owner = new_owner
    char.save()
    return redirect('character_add_skills', char.id)

def char_swap_item(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    it1 = get_object_or_404(models.CharItems, id=kwargs['it1_id'])
    it1D = get_object_or_404(models.Items, name=it1.name)
    it2 = get_object_or_404(models.Eq, id=kwargs['it2_id'])
    it2D = get_object_or_404(models.Items, name=it2.name)

    if it1D.type.lower() == "shield" and it1.hand.lower() == "right":
        allow_class = ["barbarzyńca: droga rosomaka"]
        try:
            leftItem = models.CharItems.objects.filter(character=char.name, hand="Left").first()
            leftItemDesc = get_object_or_404(models.Items, name=leftItem.name)     
            if leftItemDesc.dualHanded and char.chosen_class.lower() not in allow_class:
                messages.error(request, 'Only shield is avaible as additional weapon in this case!')
                return redirect('character_detail', char.id)                       
        except:
            pass
    
    if it2D.dualHanded and it1.hand.lower() != 'side':
        if it1.hand.lower() == 'right':
            messages.error(request, 'Dual-handed weapon must be added to left hand when right hand is empty.')
            return redirect('character_detail', char.id)
        else:
            if models.CharItems.objects.filter(character=char.name, hand='Right').first() not in [None,'']:
                messages.error(request, 'Dual-handed weapon must be added to left hand when right hand is empty.')
                return redirect('character_detail', char.id)

    if char.SIŁ > 0:
        max_weight = char.SIŁ*5+char.extra_capacity
    elif char.SIŁ <0:
        max_weight = 3+(char.SIŁ*0.5)+char.extra_capacity
    else:
        max_weight = 3+char.extra_capacity
                                        
    current_weight = 0
    for item in models.Eq.objects.filter(character=char.name):
        if "strzała" in item.name.lower():
            try:
                if models.CharItems.objects.filter(character=char.name, hand="Side").first().name=="Kolczan":
                    pass
                else:
                    current_weight += item.weight 
            except:
                current_weight += item.weight 
        elif "pocisk" in item.name.lower():
            try:
                allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                init_hands = [
                    models.CharItems.objects.filter(character=char.name, hand="Left").first(),
                    models.CharItems.objects.filter(character=char.name, hand="Right").first(),
                    models.CharItems.objects.filter(character=char.name, hand="Side").first()
                    ]
                hands = []
                for hand in init_hands:
                    try:
                        hands.append(hand.name)
                    except:
                        pass
                canPassWeight = any(item in allowed_items for item in hands)
                if canPassWeight:
                    pass
                else:
                    current_weight += item.weight 
            except:
                print(traceback.format_exc())
                current_weight += item.weight 
        else:
            current_weight += item.weight       

    if it1D.weight-it2D.weight+current_weight > max_weight:
        messages.error(request, f'Not enough space in equipment for {it1D.name}, {(it1D.weight-it2D.weight+current_weight)-max_weight}kg too heavy :(')
        return redirect('character_detail', char.id)

    if it1D.type != "Mount Armor":
        models.Eq.objects.create(
            owner=char.owner,
            character=char.name,
            name=it1.name,
            type=it1D.type,
            weight=it1D.weight,
            durability=it1.durability
        )

    if it1D.skillEffects != None:
        for effect in it1D.skillEffects.split(';'):
            effect = effect.split("-")
            models.Effects.objects.filter(character=char.name, name=effect[0]).first().delete()
    
    if it2D.type == 'Animal':
        char.extra_capacity = it2D.diceBonus
    
    it1.name = it2.name
    it1.durability = it2.durability
    it1.save()

    if it2D.skillEffects != None:
        for effect in it2D.skillEffects.split(';'):
            effect = effect.split("-")

            models.Effects.objects.create(
                owner = char.owner,
                character=char.name,
                name = effect[0],
                bonus = effect[1],
                time = effect[2]
            )    
    
    if it2D.type != "Mount Armor":
        it2.delete()
    
    return redirect('character_detail', char.id)
@user_passes_test(lambda u: u.is_superuser)
def end_round(request, **kwargs):
    msg = 'Deleted: '
    for effect in models.Effects.objects.all():
        if effect.time < 100:
            effect.time -= 1
            if effect.time <= 0:
                msg += f"{effect.character}-{effect.name}; "
                effect.delete()
            else:
                effect.save()
    if msg != 'Deleted: ':
        messages.warning(request, msg)
    return redirect('gm_panel')

class ItemsView(ListView):
    model = models.Items
    template_name = 'items.html'
    context_object_name = 'items'
    ordering = ['name']
    
    def get_queryset(self):
        queryset = []
        value = self.request.GET.get('search')
        char_id = self.kwargs['char_id']
        if char_id != 0:
            self.character = models.Character.objects.filter(id=char_id).first()
        else:
            self.character = None

        if self.character == None:
            if value:
                if self.request.user.is_superuser:
                    queryset = models.Items.objects.filter((Q(name__icontains=value) | Q(desc__icontains=value))).order_by('rarity')
                else:
                    queryset = models.Items.objects.filter((Q(name__icontains=value) | Q(desc__icontains=value)), found=True).order_by('rarity')
        else:
            self.singlehand = []
            self.twohand = []
            self.animals = []
            self.armor_dict = {'helmet': [], 'torso': [], 'boots': [], 'gloves': [], 'amulets': [], 'other': []}
            
            for item in models.Eq.objects.filter(character=self.character.name):
                item_obj = get_object_or_404(models.Items, name=item.name)
                queryset.append({'id': item_obj.id,
                                 'eq_id': item.id, 
                                 'rarity': item_obj.rarity, 
                                 'found': item_obj.found, 
                                 'name': item.name, 
                                 'dur': item.durability, 
                                 'amount': item.amount, 
                                 'max_dur': item_obj.maxDurability,
                                 'type': item_obj.type,
                                 'price': item_obj.price}
                                )
                
                if item_obj.type.lower() in self.armor_dict.keys():
                    for item_type in self.armor_dict:
                        if item_obj.type.lower() == item_type:
                            self.armor_dict[item_type].append(item_obj.__dict__ | {'dur': item.durability, 'max_dur': item_obj.maxDurability})
                else:
                    if item_obj.type == 'Animal':
                        self.animals.append(item_obj.__dict__ | {'dur': item.durability, 'max_dur': item_obj.maxDurability})
                    elif item_obj.dualHanded == False:
                        self.singlehand.append(item_obj.__dict__ | {'dur': item.durability, 'max_dur': item_obj.maxDurability})
                    else:
                        self.twohand.append(item_obj.__dict__ | {'dur': item.durability, 'max_dur': item_obj.maxDurability})
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        names = ['items_helmet','items_torso','items_boots','items_gloves','items_amulets','items_other']
        types = ['Helmet','Torso','Boots','Gloves','Amulet','Other']
        
        if self.character == None:
            if self.request.user.is_superuser:
                context['items_singlehand'] = models.Items.objects.filter(dualHanded=False).order_by('rarity').exclude(type__in=types)
                context['items_twohand'] = models.Items.objects.filter(dualHanded=True).order_by('rarity')   
                context['animals'] =  models.Items.objects.filter(type='Animal').order_by('rarity')
                context['animals'] |=  models.Items.objects.filter(type='Mount Armor').order_by('rarity')
            else:
                context['items_singlehand'] = models.Items.objects.filter(dualHanded=False, found=True).order_by('rarity').exclude(type__in=types)
                context['items_twohand'] = models.Items.objects.filter(dualHanded=True, found=True) .order_by('rarity')
                context['animals'] =  models.Items.objects.filter(type='Animal', found=True).order_by('rarity')
                context['animals'] |=  models.Items.objects.filter(type='Mount Armor', found=True).order_by('rarity')
            
            for x in range(len(names)):
                if self.request.user.is_superuser:
                    context[names[x]] = models.Items.objects.filter(type=types[x]).order_by('rarity')
                else:
                    context[names[x]] = models.Items.objects.filter(type=types[x], found=True).order_by('rarity')
        else:
            
            items_weight = 0
            for item in models.Eq.objects.filter(character=self.character.name):
                if "strzała" in item.name.lower():
                    try:
                        if models.CharItems.objects.filter(character=self.character.name, hand="Side").first().name=="Kolczan":
                            pass
                        else:
                            items_weight += item.weight 
                    except:
                        items_weight += item.weight 
                elif "pocisk" in item.name.lower():
                    try:
                        allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                        init_hands = [
                            models.CharItems.objects.filter(character=self.character.name, hand="Left").first(),
                            models.CharItems.objects.filter(character=self.character.name, hand="Right").first(),
                            models.CharItems.objects.filter(character=self.character.name, hand="Side").first()
                            ]
                        hands = []
                        for hand in init_hands:
                            try:
                                hands.append(hand.name)
                            except:
                                pass
                        canPassWeight = any(item in allowed_items for item in hands)
                        if canPassWeight:
                            pass
                        else:
                            items_weight += item.weight 
                    except:
                        print(traceback.format_exc())
                        items_weight += item.weight 
                else:
                    items_weight += item.weight 
            
            if self.character.SIŁ > 0:
                max_weight = self.character.SIŁ*5+self.character.extra_capacity
            elif self.character.SIŁ < 0:
                max_weight = 3+(self.character.SIŁ*0.5)+self.character.extra_capacity
            else:
                max_weight = 3+self.character.extra_capacity
            
            charisma = self.character.CHAR
            for mod in models.Mods.objects.filter(character=self.character.name, field="CHAR"):
                charisma += mod.value
            for item in models.CharItems.objects.filter(character=self.character.name):
                desc = get_object_or_404(models.Items, name=item.name)
                try:
                   if "CHAR" in desc.skillStats:
                       for stat in desc.skillStats.split(";"):
                           if stat.startswith("CHAR"): charisma += int(f"{stat[4]}{stat[5]}")
                except:
                    pass
            
            context['charisma'] = charisma
            context['current_weight'] = items_weight
            context['max_weight'] = max_weight
            context['items_singlehand'] = self.singlehand
            context['items_twohand'] = self.twohand
            context['animals'] = self.animals
            context['items_helmet'] = self.armor_dict['helmet']
            context['items_torso'] = self.armor_dict['torso']
            context['items_gloves'] = self.armor_dict['gloves']
            context['items_boots'] = self.armor_dict['boots']
            context['items_amulets'] = self.armor_dict['amulets']
            context['items_other'] = self.armor_dict['other']
            context['all_items'] = models.Items.objects.filter(found=True).order_by('name')
            context['player_items'] = models.Eq.objects.filter(character=self.character.name).values()
            context['characters'] = models.Character.objects.filter(hidden=False).values()
            context['character'] = self.character
        return context

class ItemDetailView(DetailView):
    model = models.Items
    template_name = 'item_detail.html'

    def get_object(self,queryset=None):
        item_id = self.kwargs.get('id')
        return get_object_or_404(models.Items, id=item_id)
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()

        types = {
            "Helmet": [1.5, 2.5],
            "Torso": [4,7],
            "Boots": [0.5, 1.1],
            "Gloves": [1, 2]
        }

        weight_type = ''
        for type in types:
            if item.type == type:
                if item.weight < types[type][0]:
                    weight_type = "Light"
                elif item.weight < types[type][1]:
                    weight_type = "Medium"
                else:
                    weight_type = "Heavy"

        if weight_type != '':
            context['weight_type'] = weight_type
        context['item'] = item

        return context

class changeItemFoundState(APIView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            state = kwargs['state']
            item_id = kwargs['id']
            char_id = kwargs['char_id']

            item = get_object_or_404(models.Items, id=item_id)

            try:
                item.found = bool(state)
            except:
                raise Http404('changeItemFoundState at views; cannot state to bool')
            
            item.save()
            
        return redirect(f'/dunnorpg/items/ch{char_id}')

class ClassesView(ListView):
    model = models.Classes
    template_name = 'classes.html'  # Update to the template you use for displaying the list
    context_object_name = 'classes'  # Context variable to use in the template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Extract unique categories from the classes
        unique_categories = models.Classes.objects.values_list('category', flat=True).distinct()
        context['unique_categories'] = unique_categories
        return context

class ClassView(DetailView):
    model = models.Classes
    template_name = 'class.html'

    def get_object(self,queryset=None):
        class_id = self.kwargs.get('id')
        return get_object_or_404(models.Classes, id=class_id)
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        chosen_class = self.get_object()

        chosen_class.armor_weight = chosen_class.armor_weight.replace("light","Lekki")
        chosen_class.armor_weight = chosen_class.armor_weight.replace("medium","Średni")
        chosen_class.armor_weight = chosen_class.armor_weight.replace("heavy","Ciężki")
        chosen_class.armor_weight = chosen_class.armor_weight.replace("all","Każdy")
        chosen_class.armor_weight = chosen_class.armor_weight.split(";")

        chosen_class.skills = chosen_class.skills.split(";")
        for skill in chosen_class.skills:
            try:
                index = chosen_class.skills.index(skill)
                lvl = skill[-1]
                chosen_class.skills[index] = f"{skill[:-1]}-{lvl}"
            except:
                pass
        
        chosen_class.effects = chosen_class.effects.split(";")
        for effect in chosen_class.effects:
            try:
                index = chosen_class.effects.index(effect)
                if effect.lower().endswith("m"):
                    lvl = effect[-2]
                    chosen_class.effects[index] = f"{effect[:-3]}(-{lvl})"
                else:
                    lvl = effect[-1]
                    chosen_class.effects[index] = f"{effect[:-2]}(+{lvl})"
            except:
                pass

        chosen_class.mods = chosen_class.mods.split(";")

        context['class'] = chosen_class

        return context

class RacesView(ListView):
    model = models.Races
    template_name = 'races.html'  # Update to the template you use for displaying the list
    context_object_name = 'races'  # Context variable to use in the template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class RaceView(DetailView):
    model = models.Races
    template_name = 'race.html'

    def get_object(self,queryset=None):
        race_id = self.kwargs.get('id')
        return get_object_or_404(models.Races, id=race_id)
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        chosen_race = self.get_object()

        chosen_race.Skills = chosen_race.Skills.split(";")
        for skill in chosen_race.Skills:
            try:
                index = chosen_race.Skills.index(skill)
                lvl = skill[0]
                chosen_race.Skills[index] = f"{skill[1:]}-{lvl}"
            except:
                pass
        
        """ #No effects for races yet
        chosen_race.effects = chosen_race.effects.split(";")
        for effect in chosen_race.effects:
            try:
                index = chosen_race.effects.index(effect)
                if effect.lower().endswith("m"):
                    lvl = effect[-2]
                    chosen_race.effects[index] = f"{effect[:-3]}(-{lvl})"
                else:
                    lvl = effect[-1]
                    chosen_race.effects[index] = f"{effect[:-2]}(+{lvl})"
            except:
                pass
        """

        chosen_race.statPlus = chosen_race.statPlus.split(";")
        chosen_race.statPlus = [
            f"INT(+{chosen_race.statPlus[0]})",
            f"SIŁ(+{chosen_race.statPlus[1]})",
            f"ZRE(+{chosen_race.statPlus[2]})",
            f"CHAR(+{chosen_race.statPlus[3]})",
            f"CEL(+{chosen_race.statPlus[4]})"
        ]
        chosen_race.statMinus = chosen_race.statMinus.split(";")
        chosen_race.statMinus = [
            f"INT(-{chosen_race.statMinus[0]})",
            f"SIŁ(-{chosen_race.statMinus[1]})",
            f"ZRE(-{chosen_race.statMinus[2]})",
            f"CHAR(-{chosen_race.statMinus[3]})",
            f"CEL(-{chosen_race.statMinus[4]})"
        ]

        chosen_race.weaponsPreffered = chosen_race.weaponsPreffered.split(";")
        chosen_race.weaponsUnliked = chosen_race.weaponsUnliked.split(";")

        context['race'] = chosen_race

        return context

class changeItemFoundState(APIView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            state = kwargs['state']
            item_id = kwargs['id']
            char_id = kwargs['char_id']

            item = get_object_or_404(models.Items, id=item_id)

            try:
                item.found = bool(state)
            except:
                raise Http404('changeItemFoundState at views; cannot state to bool')
            
            item.save()
            
        return redirect(f'/dunnorpg/items/ch{char_id}')

class makeRequest(APIView):
    def get(self, request, **kwargs):
        try:
            models.Requests.objects.create(
                    from_user = request.user,
                    char_id = kwargs['char_id'],
                    objects_model = kwargs['objects_model'],
                    object1_id = kwargs['object1_id'],
                    object2_id = kwargs['object2_id'],
                    model = kwargs['model'],
                    field = kwargs['field'],
                    title = kwargs['title']            
            )
            messages.success(request,'Request created successfully!')
        except:
            messages.error(request, 'Request creation failed!')
        if kwargs['char_id'] == 0:
            kwargs['char_id'] = ''
        id = kwargs['char_id']
        reverse_url = reverse(kwargs['to_reverse'], args=(id,))
        return redirect(reverse_url)
    
class RequestHandling(APIView):
    def get(self, request, **kwargs):
        if request.user.is_superuser:
            
            if kwargs['status'] == 0:
                if kwargs['all']:
                    for rq_object in models.Requests.objects.all():
                        rq_object.delete()
                else:
                    get_object_or_404(models.Requests, id=kwargs['rq_id']).delete()
                    
            else:
                if kwargs['all']:
                    for rq_object in models.Requests.objects.all():
                        rq_op = rq_object.title.split('-')[0].lower()
                        for listed_model in apps.get_models():
                            if listed_model.__name__ == rq_object.model:
                                obj1 = listed_model.objects.filter(id=rq_object.object1_id).first()
                                obj2 = listed_model.objects.filter(id=rq_object.object2_id).first()
                                
                                if rq_op == 'downgrade':
                                    if obj1 != None:
                                        obj1.durability -= 1
                                        obj1.save()
                                        rq_object.delete()
                                elif rq_op == 'change_to':
                                    val = rq_object.title.split('-')[1]
                                    char = get_object_or_404(models.Character, id=rq_object.char_id)
                                    if rq_object.field == 'hp':
                                        char.HP = val
                                    elif rq_object.field == 'coins':
                                        char.coins = val
                                    char.save()
                                    rq_object.delete()
                                elif rq_op == "eq_add":
                                    dur = rq_object.title.split('-')[1][:-3]
                                    char = get_object_or_404(models.Character, id=rq_object.char_id)
                                    itemDesc = models.Items.objects.get(id=rq_object.object1_id)

                                    if char.SIŁ > 0:
                                        max_weight = char.SIŁ*5+char.extra_capacity
                                    elif char.SIŁ <0:
                                        max_weight = 3+(char.SIŁ*0.5)+char.extra_capacity
                                    else:
                                        max_weight = 3+char.extra_capacity
                                        
                                    current_weight = 0
                                    for item in models.Eq.objects.filter(character=char.name):
                                        if "strzała" in item.name.lower():
                                            try:
                                                if models.CharItems.objects.filter(character=char.name, hand="Side").first().name=="Kolczan":
                                                    pass
                                                else:
                                                    current_weight += item.weight 
                                            except:
                                                current_weight += item.weight 
                                        elif "pocisk" in item.name.lower():
                                            try:
                                                allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                                                init_hands = [
                                                    models.CharItems.objects.filter(character=char.name, hand="Left").first(),
                                                    models.CharItems.objects.filter(character=char.name, hand="Right").first(),
                                                    models.CharItems.objects.filter(character=char.name, hand="Side").first()
                                                    ]
                                                hands = []
                                                for hand in init_hands:
                                                    try:
                                                        hands.append(hand.name)
                                                    except:
                                                        pass
                                                canPassWeight = any(item in allowed_items for item in hands)
                                                if canPassWeight:
                                                    pass
                                                else:
                                                    current_weight += item.weight 
                                            except:
                                                print(traceback.format_exc())
                                                current_weight += item.weight 
                                        else:
                                            current_weight += item.weight 

                                    if current_weight+itemDesc.weight <= max_weight:
                                        models.Eq.objects.create(
                                            owner = char.owner,
                                            character = char.name,
                                            name = itemDesc.name,
                                            type = itemDesc.type,
                                            weight = itemDesc.weight,
                                            durability = dur,
                                            amount = 1
                                        )
                                        rq_object.delete()
                                    else:
                                        messages.error(request, f'Not enough space for {itemDesc.name}. ({current_weight}/{max_weight}kg)')
                else:  
                    rq = get_object_or_404(models.Requests, id=kwargs['rq_id'])
                    rq_op = rq.title.split('-')[0].lower()       
                    for listed_model in apps.get_models():
                        if listed_model.__name__ == rq.model:
                            obj1 = listed_model.objects.filter(id=rq.object1_id).first()
                            obj2 = listed_model.objects.filter(id=rq.object2_id).first()
                            
                            if rq_op == 'downgrade':
                                if obj1 != None:
                                    obj1.durability -= 1
                                    obj1.save()
                                    rq.delete()
                            elif rq_op == 'change_to':
                                val = rq.title.split('-')[1]
                                char = get_object_or_404(models.Character, id=rq.char_id)
                                if rq.field == 'hp':
                                    char.HP = val
                                elif rq.field == 'coins':
                                    char.coins = val
                                char.save()
                                rq.delete()                                    
                            elif rq_op == "eq_add":
                                dur = rq.title.split('-')[1][:-3]
                                char = get_object_or_404(models.Character, id=rq.char_id)
                                itemDesc = models.Items.objects.get(id=rq.object1_id)
                                
                                if char.SIŁ > 0:
                                    max_weight = char.SIŁ*5+char.extra_capacity
                                elif char.SIŁ <0:
                                    max_weight = 3+(char.SIŁ*0.5)+char.extra_capacity
                                else:
                                    max_weight = 3+char.extra_capacity
                                    
                                current_weight = 0
                                for item in models.Eq.objects.filter(character=char.name):
                                    if "strzała" in item.name.lower():
                                        try:
                                            if models.CharItems.objects.filter(character=char.name, hand="Side").first().name=="Kolczan":
                                                pass
                                            else:
                                                current_weight += item.weight 
                                        except:
                                            current_weight += item.weight 
                                    elif "pocisk" in item.name.lower():
                                        try:
                                            allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                                            init_hands = [
                                                models.CharItems.objects.filter(character=char.name, hand="Left").first(),
                                                models.CharItems.objects.filter(character=char.name, hand="Right").first(),
                                                models.CharItems.objects.filter(character=char.name, hand="Side").first()
                                                ]
                                            hands = []
                                            for hand in init_hands:
                                                try:
                                                    hands.append(hand.name)
                                                except:
                                                    pass
                                            canPassWeight = any(item in allowed_items for item in hands)
                                            if canPassWeight:
                                                pass
                                            else:
                                                current_weight += item.weight 
                                        except:
                                            print(traceback.format_exc())
                                            current_weight += item.weight 
                                    else:
                                        current_weight += item.weight 

                                if current_weight+itemDesc.weight <= max_weight:
                                    models.Eq.objects.create(
                                        owner = char.owner,
                                        character = char.name,
                                        name = itemDesc.name,
                                        type = itemDesc.type,
                                        weight = itemDesc.weight,
                                        durability = dur,
                                        amount = 1
                                    )
                                    rq.delete()
                                else:
                                    messages.error(request, f'Not enough space for {itemDesc.name}. ({current_weight}/{max_weight}kg)')   
        if "/gmpanel/" not in request.META['HTTP_REFERER']:
            return redirect(request.META['HTTP_REFERER'])                     
        return redirect('/dunnorpg/gmpanel')

class AddEffect(APIView):
    def post(self,request,**kwargs):
        if request.user.is_superuser:
            data = request.POST
            char = get_object_or_404(models.Character, id=data['character'])
            effect = get_object_or_404(models.Effects_Decs, id=data['name'])
            models.Effects.objects.create(
                owner = char.owner,
                character = char.name,
                name = effect.name,
                bonus = data['bonus'],
                time = data['time']
            )
            messages.warning(request, f'Added {effect.name} to {char.name}.')
        return redirect('gm_panel')

class GMPanel(FormView):
    model = models.Requests
    template_name = 'gm_panel.html'
    form_class = AddEqItemForm
    success_url = reverse_lazy('gm_panel')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['requests'] = models.Requests.objects.all()
        context['effect_form'] = AddEffectForm

        return context
    
    def form_valid(self, form):
        override = form['override'].value()
        form_data = form.save(commit=False)
        
        character = models.Character.objects.get(pk=form_data.character)
        form_data.owner = character.owner
        form_data.character = character.name
        
        item = models.Items.objects.get(pk=form_data.name)
        form_data.name = item.name
        form_data.type = item.type
        form_data.weight = item.weight*form_data.amount
        
        if not override:
            if character.SIŁ > 0:
                max_weight = character.SIŁ*5+character.extra_capacity
            elif character.SIŁ < 0:
                max_weight = 3 + (character.SIŁ*0.5)+character.extra_capacity
            else:
                max_weight = 3+character.extra_capacity
                
            current_weight = 0
            for eq_item in models.Eq.objects.filter(character=character.name):
                if "strzała" in eq_item.name.lower():
                    try:
                        if models.CharItems.objects.filter(character=character.name, hand="Side").first().name=="Kolczan":
                            pass
                        else:
                            current_weight += eq_item.weight 
                    except:
                        current_weight += eq_item.weight 
                elif "pocisk" in eq_item.name.lower():
                    try:
                        allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                        init_hands = [
                            models.CharItems.objects.filter(character=self.character.name, hand="Left").first(),
                            models.CharItems.objects.filter(character=self.character.name, hand="Right").first(),
                            models.CharItems.objects.filter(character=self.character.name, hand="Side").first()
                            ]
                        hands = []
                        for hand in init_hands:
                            try:
                                hands.append(hand.name)
                            except:
                                pass
                        canPassWeight = any(item in allowed_items for item in hands)
                        if canPassWeight:
                            pass
                        else:
                            current_weight += eq_item.weight 
                    except:
                        print(traceback.format_exc())
                        current_weight += eq_item.weight 
                else:
                    current_weight += eq_item.weight 
                
            item_weight = item.weight * form_data.amount
            if current_weight + item_weight > max_weight:
                messages.error(self.request, 'Not enough space.')
                return redirect('gm_panel')
        
        try:
            existing_item = get_object_or_404(models.Eq, name=item.name, character=character.name, durability=form_data.durability)
            existing_item.amount += form_data.amount
            existing_item.weight += item_weight
            existing_item.save()
        except:
            form_data.save()

        messages.success(self.request, f"{item.name} added to {character.name}.")
        return super().form_valid(form)
    
class Info(APIView):
    template_name = 'info.html'
    renderer_classes = [TemplateHTMLRenderer]
    def get(self,request):
        
        context = {
            
        }
        
        return Response(context)
#Info options:    
class AccRules(APIView):
    template_name = 'acc-rules.html'
    renderer_classes = [TemplateHTMLRenderer]
    def get(self,request):
        
        context = {
            
        }
        
        return Response(context)
class InfoEffects(ListView):
    model = models.Effects_Decs
    template_name = 'info-effects.html'
    context_object_name = 'effects'
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        value = self.request.GET.get('search-input')

        if value:
            search_fields = [field.name for field in models.Effects_Decs._meta.fields]
            query = Q()

            for field in search_fields:
                query |= Q(**{f"{field}__icontains": value})

            queryset = queryset.filter(query)

        return queryset
class CityView(ListView):
    model = models.Cities
    template_name = 'city.html'

    def get_object(self,queryset=None):
        return models.Cities.objects.filter(visiting=True).first()
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        city = self.get_object()
        is_empty = True if city == None else False

        context['is_empty'] = is_empty
        if not is_empty:
            items = city.items.split(';')
            items.sort()
            armor_types = ['Helmet','Torso','Gloves','Boots']
            
            armor=[]
            amulets=[]
            weaponry_siglehand=[]
            weaponry_twohand=[]
            potions = []
            other = []
            animals = []
            amounts = {}
            
            for item in items:
                item_name = item.split("|")[0]

                amount = 1
                try:
                    amount = item.split("|")[1]
                except:
                    pass

                if int(amount) == 0:
                    continue

                item = models.Items.objects.filter(name=item_name).first()

                if item != None:
                    if not item.found:
                        item.found = True
                        item.save()

                    amounts[item.name] = amount
                    if item.type == 'Amulet':
                        amulets.append(item.name)
                    elif item.type == 'Other':
                        if item.name.split(' ')[0] in ['Eliksir','Mikstura']:
                            potions.append(item.name)
                        else:   
                            other.append(item.name)
                    elif item.type == 'Animal' or item.type.lower() == 'mount armor':
                        animals.append(item.name)
                    else:
                        if item.type in armor_types:
                            armor.append(item.name)
                        else:
                            if item.dualHanded:
                                weaponry_twohand.append(item.name)
                            else:
                                weaponry_siglehand.append(item.name)            
            
            x5packets = []
            x10packets = ["Strzała","Pocisk do broni prochowej"]
            
            context['weaponry_singlehand'] = weaponry_siglehand
            context['weaponry_twohand'] = weaponry_twohand
            context['armor'] = armor
            context['amulets'] = amulets
            context['potions'] = potions
            context['animals'] = animals
            context['other'] = other
            context['city'] = city
            context['x5packets'] = x5packets
            context['x10packets'] = x10packets
            context['amounts'] = amounts
            if self.request.user.is_superuser:
                context['characters'] = models.Character.objects.all()
            else:
                context['characters'] = models.Character.objects.filter(owner=self.request.user, hidden=False)


        return context       
class BuyItem(APIView):
    def get(self,request,**kwargs):
        item = get_object_or_404(models.Items, id=kwargs['item_id'])
        character = get_object_or_404(models.Character, id=kwargs['character_id'])
        city = get_object_or_404(models.Cities, visiting=True)
        item_amount = kwargs['amount']

        if character.SIŁ > 0:
            max_weight = character.SIŁ*5+character.extra_capacity
        elif character.SIŁ < 0:
            max_weight = 3+(character.SIŁ*0.5)+character.extra_capacity
        else:
            max_weight = 3 +character.extra_capacity
            
        current_weight = 0
        for eq_item in models.Eq.objects.filter(character=character.name):
            if "strzała" in eq_item.name.lower():
                try:
                    if models.CharItems.objects.filter(character=character.name, hand="Side").first().name=="Kolczan":
                        pass
                    else:
                        current_weight += eq_item.weight 
                except:
                    current_weight += eq_item.weight 
            elif "pocisk" in eq_item.name.lower():
                try:
                    allowed_items = ["Pas na amunicje","Zmodyfikowana Lustrzana Tarcza"]
                    init_hands = [
                        models.CharItems.objects.filter(character=self.character.name, hand="Left").first(),
                        models.CharItems.objects.filter(character=self.character.name, hand="Right").first(),
                        models.CharItems.objects.filter(character=self.character.name, hand="Side").first()
                        ]
                    hands = []
                    for hand in init_hands:
                        try:
                            hands.append(hand.name)
                        except:
                            pass
                    canPassWeight = any(item in allowed_items for item in hands)
                    if canPassWeight:
                        pass
                    else:
                        current_weight += eq_item.weight 
                except:
                    print(traceback.format_exc())
                    current_weight += eq_item.weight 
            else:
                current_weight += eq_item.weight  

        if current_weight+item.weight*item_amount <= max_weight:
            price = item.price*2
            charisma = character.CHAR
            for mod in models.Mods.objects.filter(character=character.name, field="CHAR"):
                charisma += mod.value
            for char_item in models.CharItems.objects.filter(character=character.name):
                desc = get_object_or_404(models.Items, name=char_item.name)
                try:
                    if "CHAR" in desc.skillStats:
                        for stat in desc.skillStats.split(";"):
                            if stat.startswith("CHAR"): charisma += int(f"{stat[4]}{stat[5]}")
                except:
                    pass

            char_bonus = price * (charisma * 2) // 100
            price -= char_bonus

            if character.coins >= price:
                character.coins -= price
                character.save()
                
                try:
                    existing_item = get_object_or_404(models.Eq, name=item.name, character=character.name)
                    existing_item.amount += item_amount
                    existing_item.weight += item.weight*item_amount
                    existing_item.save()                    
                except:
                    models.Eq.objects.create(
                        owner = character.owner,
                        character = character.name,
                        name = item.name,
                        type = item.type,
                        weight = item.weight*item_amount,
                        durability = item.maxDurability,
                        amount = item_amount
                    )

                city_items = city.items.split(";")
                for ct_item in city_items:
                    ct_item_name = ct_item.split("|")[0]
                    if ct_item_name == item.name:
                        index = city_items.index(ct_item)
                        try:
                            amount = ct_item.split("|")[1]
                        except:
                            amount = 1

                        new_amount = int(amount)-int(item_amount)
                        ct_new_item = f"{ct_item_name}|{new_amount}"
                        city_items[index] = ct_new_item

                city.items = ';'.join(city_items)
                city.save()

                messages.success(request,f'[{character.name}] Zakupiono {item.name} za {price} monet.')
            else:
                messages.error(request, f'Za mało monet. {character.name} ma ich {character.coins}, a potrzeba {price}.')
        else:
            messages.error(request, f'Za mało miejsca! Nosisz już {current_weight}/{max_weight}kg.')

        return redirect('/dunnorpg/city')

class healCharacter(APIView):
    def get(self,request,**kwargs):
        character = get_object_or_404(models.Character, id=kwargs['char_id'])
        val = kwargs['val']

        if character.HP + val <= character.fullHP:
            if val < 0:
                messages.error(request, 'Value for healing must be at least 0.')
                
            elif character.coins < val:
                messages.error(request, 'Not enough money!')
            else:
                character.HP += val
                character.coins -= val
                character.save()
                messages.success(request, f'{character.name} has been healed succesfully!')
        else:
            messages.error(request, f"Value you given doesn't fit {character.name} health points!")
        return redirect('/dunnorpg/city')

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"
    
def view_404(request, exception):
    return render(request, '404.html', status=404)