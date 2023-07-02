from typing import Any, Dict
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.apps import apps
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.generic import FormView, ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from DunnoRPG.serializers import (CharacterSerializer, ItemSerializer,
                                  SkillsDecsSerializer, SkillsSerializer)

from . import models
from .forms import CharacterForm, CharacterSkillsForm


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

            character.points_left = chosen_race.points_limit - (character.INT+character.SIŁ+character.ZRE+character.CHAR+character.CEL)

            pluses = chosen_race.statPlus.split(';')
            minuses = chosen_race.statMinus.split(';')
            character.INT += int(pluses[0])-int(minuses[0])
            character.SIŁ += int(pluses[1])-int(minuses[1])
            character.ZRE += int(pluses[2])-int(minuses[2])
            character.CHAR += int(pluses[3])-int(minuses[3])
            character.CEL += int(pluses[4])-int(minuses[4])

            character.fullHP = character.HP
                
            character.weaponBonus = chosen_race.weaponsBonus
            character.preferredWeapons = chosen_race.weaponsPreffered
            character.unlikedWeapons = chosen_race.weaponsUnliked

            character.save()

            skills = models.Skills.objects
            for skill in chosen_race.Skills.split(';'):
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
        chosen_character = get_object_or_404(models.Character, id=id).name
        character_skills_queryset = models.Skills.objects.all().filter(owner=user, character=chosen_character).values() 
        
        return character_skills_queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_user = self.request.user
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

        context['user'] = current_user
        context['character'] = chosen_character
        context['character_id'] = id
        context['character_stats'] = character_stats
        context['skills_count'] = skills_points
        context['skills_count_magical'] = magical_skills_points
        context['form'] = CharacterSkillsForm()

        return context            
    def form_valid(self, form):
        current_user = self.request.user
        id = self.kwargs['id']
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
            skill_to_add.owner = current_user
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
        
        skills = models.Skills.objects.all().filter(owner=self.request.user,character=serializer.data['name']).values()
        race = models.Races.objects.all().filter(name=serializer.data['race']).values()[0]
        mods = models.Mods.objects.all().filter(owner=self.request.user,character=serializer.data['name']).values()

        for skill in skills:
            skill_description = models.Skills_Decs.objects.all().filter(name=skill['skill']).values()[0]
            skill['original_id'] = skill_description['id']
            skill['original_desc'] = skill_description['desc']
            skill['level_desc'] = skill_description[f"level{skill['level']}"]

        
        context['helmet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Helmet').first()
        context['torso'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Torso').first()
        context['gloves'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Gloves').first()
        context['boots'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Boots').first()
        context['amulet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Amulet').first()
        context['leftItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Left').first()
        context['rightItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Right').first()
        context['sideItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Side').first()
        context['chosen_character'] = [serializer.data] 
        context['mods'] = mods
        context['skills'] = skills
        context['race_desc'] = race['desc']

        return context 

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
            #if int also check if magical_skills>0, also might be problem when e.g. downgrading SIŁ from 2 to 1 when skill needs 2 SIŁ
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

class ItemsView(ListView):
    model = models.Items
    template_name = 'items.html'
    context_object_name = 'items'
    ordering = ['name']
    armor_types = ['Helmet','Torso','Boots','Gloves','Amulet']
    
    def get_queryset(self):
        queryset = []
        value = self.request.GET.get('search')
        char_id = self.kwargs['char_id']
        if char_id != 0:
            self.character = models.Character.objects.filter(id=char_id).first().name
        else:
            self.character = None

        if self.character == None:
            if value:
                if self.request.user.is_superuser:
                    queryset = models.Items.objects.filter((Q(name__icontains=value) | Q(desc__icontains=value))).order_by('rarity')
                else:
                    queryset = models.Items.objects.filter((Q(name__icontains=value) | Q(desc__icontains=value)), found=True).order_by('rarity')
        else:
            for item in models.Eq.objects.filter(character=self.character):
                item_obj = get_object_or_404(models.Items, name=item.name)
                queryset.append({'id': item_obj.id, 'rarity': item_obj.rarity, 'found': item_obj.found, 'name': item.name, 'dur': item.durability, 'max_dur': item_obj.maxDurability})
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        #context to be updated to give items from character Eq like above
        
        names = ['items_helmet','items_torso','items_boots','items_gloves','items_amulets','items_other']
        types = ['Helmet','Torso','Boots','Gloves','Amulet','Other']
        
        if self.request.user.is_superuser:
            context['items_singlehand'] = models.Items.objects.filter(dualHanded=False).order_by('rarity').exclude(type__in=types)
            context['items_twohand'] = models.Items.objects.filter(dualHanded=True).order_by('rarity')    
        else:
            context['items_singlehand'] = models.Items.objects.filter(dualHanded=False, found=True).order_by('rarity').exclude(type__in=types)
            context['items_twohand'] = models.Items.objects.filter(dualHanded=True, found=True) .order_by('rarity')
        
        for x in range(len(names)):
            if self.request.user.is_superuser:
                context[names[x]] = models.Items.objects.filter(type=types[x]).order_by('rarity')
            else:
                context[names[x]] = models.Items.objects.filter(type=types[x], found=True).order_by('rarity')
        
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

        context['item'] = item

        return context

class changeItemFoundState(APIView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superuser:
            state = kwargs['state']
            item_id = kwargs['id']

            item = get_object_or_404(models.Items, id=item_id)

            try:
                item.found = bool(state)
            except:
                print('changeItemFoundState at views; cannot state to bool')
                raise Http404('changeItemFoundState at views; cannot state to bool')
            
            item.save()
            
        return redirect('/dunnorpg/items')

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
                                
                                if obj1 != None:
                                    if rq_op == 'downgrade':
                                        obj1.durability -= 1
                                        obj1.save()
                                        rq_object.delete()
                                if obj2 != None:
                                    pass #not needed for downgrade ops
                else:  
                    rq = get_object_or_404(models.Requests, id=kwargs['rq_id'])
                    rq_op = rq.title.split('-')[0].lower()       
                    for listed_model in apps.get_models():
                        if listed_model.__name__ == rq.model:
                            obj1 = listed_model.objects.filter(id=rq.object1_id).first()
                            obj2 = listed_model.objects.filter(id=rq.object2_id).first()
                            
                            if obj1 != None:
                                if rq_op == 'downgrade':
                                    obj1.durability -= 1
                                    obj1.save()
                                    rq.delete()
                            if obj2 != None:
                                pass #not needed for downgrade ops
                    
        return redirect('/dunnorpg/gmpanel')

class GMPanel(ListView):
    model = models.Requests
    template_name = 'gm_panel.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['requests'] = models.Requests.objects.all()

        return context
    
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

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"
    
def view_404(request, exception):
    return render(request, '404.html', status=404)