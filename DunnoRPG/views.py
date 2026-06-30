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
import re
from urllib.parse import urlencode
from pathlib import Path

from DunnoRPG.serializers import (CharacterSerializer, ItemSerializer,
                                  SkillsDecsSerializer, SkillsSerializer)

from . import models
from .forms import CharacterSkillsForm, AddEqItemForm #, AddEffectForm
from .services.item_effects import apply_item_use_effects

raceSizes = {
    "S": 0.5,
    "M": 1,
    "L": 2
}

CLASS_COUNTERS = {
    "Rębacz": "Impet",
    "Juggernaut": "Napór",
    "Berserker": "Szał",
    "Kapłan bitewny Sigmara": "Zapał",
    "Snajper": "Znacznik Obserwacji",
    "Strzelec wyborowy": "Rytm Strzelecki",
    "Opętany Strzelec": "Znacznik Opętania",
    "Piromanta": "Żar",
}

def parse_free_skill(skill):
    skill = (skill or "").strip()
    if not skill:
        return None
    if "-" in skill:
        parts = skill.split("-")
        lvl = parts.pop()
        skill_name = "-".join(parts)
    elif skill[0].isdigit():
        lvl = skill[0]
        skill_name = skill[1:]
    elif skill[-1].isdigit():
        lvl = skill[-1]
        skill_name = skill[:-1]
    else:
        return None
    if not skill_name:
        return None
    return skill_name, int(lvl)

def grant_free_skill(owner, character_name, skill):
    parsed_skill = parse_free_skill(skill)
    if parsed_skill is None:
        return

    skill_name, skill_lvl = parsed_skill
    if models.Skills.objects.filter(owner=owner, character=character_name, skill=skill_name).exists():
        return

    skill_desc = get_object_or_404(models.Skills_Decs, name=skill_name)
    max_uses = getattr(skill_desc, f"useslvl{skill_lvl}", None)
    models.Skills.objects.create(
        owner=owner,
        character=character_name,
        skill=skill_name,
        category=f"{skill_lvl}free",
        level=skill_lvl,
        desc=skill_desc.desc,
        uses_left=max_uses or 0,
        source="natural_free"
    )

maxAdvs = 2
maxBigAdvs = 1

ARMOR_WEIGHT_ORDER = {
    "light": 1,
    "light+": 2,
    "medium": 3,
    "medium+": 4,
    "heavy": 5,
    "all": 999,
}
ARMOR_WEIGHT_TRANSLATE = {
    "light": "Lekki",
    "light+": "Lekki+",
    "medium": "Średni",
    "medium+": "Średni+",
    "heavy": "Ciężki"
}
ARMOR_WEIGHT_LIMITED_POSITIONS = {"helmet", "torso", "boots", "gloves"}
MOUNT_ATTACHMENT_POSITIONS = {"Mount_armor", "Mount_saddle", "Mount_horseshoes"}
MOUNT_ATTACHMENT_CATEGORIES = {
    "Mount_armor": {"animal_armor"},
    "Mount_saddle": {"animal_saddle"},
    "Mount_horseshoes": {"animal_horseshoes"},
}
MOUNT_ITEM_CATEGORIES = {"animal", "animal_armor", "animal_saddle", "animal_horseshoes"}


def get_character_max_weight(character):
    has_mount = models.CharItems.objects.filter(character=character.name, position="Mount").exists()
    item_capacity = 0
    for item in models.Eq.objects.filter(character=character.name):
        item_desc = models.Items.objects.filter(name=item.name).first()
        if item_desc:
            if (item_desc.category or "").lower() == "animal_saddle":
                continue
            item_capacity += item_desc.extra_capacity * item.amount

    for item in models.CharItems.objects.filter(character=character.name):
        if item.name:
            item_desc = models.Items.objects.filter(name=item.name).first()
            if item_desc:
                if (item_desc.category or "").lower() == "animal_saddle" and not has_mount:
                    continue
                item_capacity += item_desc.extra_capacity

    return max(10, 30 + (character.SIŁ * 7.5) + character.extra_capacity + item_capacity)


def get_character_current_weight(character):
    current_weight = 0
    for item in models.Eq.objects.filter(character=character.name):
        current_weight += item.weight

    for item in models.CharItems.objects.filter(character=character.name):
        if item.name:
            item_desc = models.Items.objects.filter(name=item.name).first()
            if item_desc:
                current_weight += item_desc.weight

    return current_weight


def move_char_item_to_eq(char_item):
    item_desc = get_object_or_404(models.Items, name=char_item.name)
    eq_item = models.Eq.objects.filter(
        character=char_item.character,
        name=char_item.name,
        durability=char_item.durability,
        additional_description=char_item.additional_description,
    ).first()

    if eq_item:
        eq_item.amount += 1
        eq_item.weight += item_desc.weight
        eq_item.save()
    else:
        models.Eq.objects.create(
            owner=char_item.owner,
            character=char_item.character,
            name=char_item.name,
            type=item_desc.type,
            weight=item_desc.weight,
            durability=char_item.durability,
            additional_description=char_item.additional_description,
        )

    if item_desc.skillEffects != None:
        for effect in item_desc.skillEffects.split(';'):
            effect = effect.split("-")
            active_effect = models.Effects.objects.filter(character=char_item.character, name=effect[0]).first()
            if active_effect:
                active_effect.delete()

    char_item.delete()


def can_character_wear_armor_weight(character, item, place):
    if place.lower() not in ARMOR_WEIGHT_LIMITED_POSITIONS:
        return True, ""
    if (item.type or "").lower() not in ARMOR_WEIGHT_LIMITED_POSITIONS:
        return True, ""

    item_armor_weight = (item.armor_weight or "").strip().lower()
    item_armor_rank = ARMOR_WEIGHT_ORDER.get(item_armor_weight)
    if item_armor_rank is None:
        return True, ""

    character_class = models.Classes.objects.filter(name=character.chosen_class).first()
    if character_class is None:
        return True, ""

    class_armor_weight = (character_class.armor_weight or "").strip().lower()
    class_armor_rank = ARMOR_WEIGHT_ORDER.get(class_armor_weight)
    if class_armor_rank is None:
        return True, ""

    if item_armor_rank > class_armor_rank:
        return False, (
            f"{character.name} nie może założyć {item.name}: typ pancerza "
            f"{ARMOR_WEIGHT_TRANSLATE[item.armor_weight]} przekracza limit klasy {ARMOR_WEIGHT_TRANSLATE[character_class.armor_weight]}."
        )

    return True, ""


def get_drunkenness_limit(character):
    #Mocna głowa increases drunkenness limit by 1 per skill level, base limit is 3
    strong_head_skill = models.Skills.objects.filter(
        character=character.name,
        skill__iexact='Mocna głowa',
    ).first()

    if strong_head_skill is None:
        return 3

    return 3 + strong_head_skill.level

ALCOHOL_MODS = (
    ("SIŁ", 1),
    ("CHAR", 1),
    ("CEL", -2),
)
ALCOHOL_DRUNK_MODS = (
    ("SIŁ", 2),
    ("CEL", -4),
)
ALCOHOL_LITE_SOURCE = "alcohol-lite"
ALCOHOL_DRUNK_SOURCE = "alcohol"
ALCOHOL_HANGOVER_SOURCE = "alcohol-hangover"
ALCOHOL_DRUNK_EFFECTS = (
    ("Utrudnienie", "Jesteś pijany", 1000, "Aktywne", "Reakcja"),
    ("Nierówny krok", "Jesteś pijany", 1000, "Aktywne", "Mobility-M1"),
)
ALCOHOL_HANGOVER_EFFECTS = (
    ("Utrudnienie", "Masz kaca", 1, "Aktywne", "Akcja"),
    ("Utrudnienie", "Masz kaca", 1, "Aktywne", "Reakcja"),
    ("Nierówny krok", "Masz kaca", 1000, "Aktywne", "Mobility-M1"),
)

def get_alcohol_state(character, alcohol_level=None, drunkenness_limit=None):
    if alcohol_level is None:
        try:
            alcohol_level = int(character.alcohol)
        except (TypeError, ValueError):
            alcohol_level = 0
    if drunkenness_limit is None:
        drunkenness_limit = get_drunkenness_limit(character)

    if alcohol_level > drunkenness_limit:
        return "Pijany"
    if alcohol_level > 0:
        return "Podpity"
    if models.Effects.objects.filter(
        owner=character.owner,
        character=character.name,
        source=ALCOHOL_HANGOVER_SOURCE,
    ).exists():
        return "Kac"
    return "Trzeźwy"

def sync_alcohol_mods(character, previous_alcohol_level=None):
    try:
        alcohol_level = int(character.alcohol)
    except (TypeError, ValueError):
        alcohol_level = 0
    if previous_alcohol_level is None:
        previous_alcohol_level = alcohol_level
    else:
        try:
            previous_alcohol_level = int(previous_alcohol_level)
        except (TypeError, ValueError):
            previous_alcohol_level = 0

    drunkenness_limit = get_drunkenness_limit(character)
    alcohol_lite_mods = models.Mods.objects.filter(
        owner=character.owner,
        character=character.name,
        source=ALCOHOL_LITE_SOURCE,
    )
    alcohol_drunk_mods = models.Mods.objects.filter(
        owner=character.owner,
        character=character.name,
        source=ALCOHOL_DRUNK_SOURCE,
    )
    alcohol_drunk_effect_names = [effect[0] for effect in ALCOHOL_DRUNK_EFFECTS]
    alcohol_drunk_effects = models.Effects.objects.filter(
        owner=character.owner,
        character=character.name,
        name__in=alcohol_drunk_effect_names,
        desc="Jesteś pijany",
        category="Aktywne",
        source=ALCOHOL_DRUNK_SOURCE,
    )

    if alcohol_level <= 0:
        alcohol_lite_mods.delete()
        alcohol_drunk_mods.delete()
        models.Effects.objects.filter(
            owner=character.owner,
            character=character.name,
            source__in=[ALCOHOL_LITE_SOURCE, ALCOHOL_DRUNK_SOURCE],
        ).delete()
        if previous_alcohol_level > drunkenness_limit:
            for name, desc, time, category, works_for in ALCOHOL_HANGOVER_EFFECTS:
                effect, _ = models.Effects.objects.get_or_create(
                    owner=character.owner,
                    character=character.name,
                    name=name,
                    desc=desc,
                    category=category,
                    works_for=works_for,
                    source=ALCOHOL_HANGOVER_SOURCE,
                    defaults={
                        "time": time,
                    },
                )
                if effect.time != time:
                    effect.time = time
                    effect.save()
        return

    if alcohol_level > drunkenness_limit:
        alcohol_lite_mods.delete()
        wanted_drunk_mods = set(ALCOHOL_DRUNK_MODS)
        for mod in alcohol_drunk_mods:
            if (mod.field, mod.value) not in wanted_drunk_mods:
                mod.delete()

        for field, value in ALCOHOL_DRUNK_MODS:
            if not alcohol_drunk_mods.filter(field=field, value=value).exists():
                models.Mods.objects.create(
                    owner=character.owner,
                    character=character.name,
                    field=field,
                    value=value,
                    source=ALCOHOL_DRUNK_SOURCE,
                )

        for name, desc, time, category, works_for in ALCOHOL_DRUNK_EFFECTS:
            effect, _ = models.Effects.objects.get_or_create(
                owner=character.owner,
                character=character.name,
                name=name,
                desc=desc,
                category=category,
                source=ALCOHOL_DRUNK_SOURCE,
                defaults={
                    "time": time,
                    "works_for": works_for,
                },
            )
            if effect.time != time or effect.works_for != works_for:
                effect.time = time
                effect.works_for = works_for
                effect.save()
        return

    alcohol_drunk_mods.delete()
    alcohol_drunk_effects.delete()
    if alcohol_level >= drunkenness_limit:
        alcohol_lite_mods.delete()
        return

    wanted_mods = set(ALCOHOL_MODS)
    for mod in alcohol_lite_mods:
        if (mod.field, mod.value) not in wanted_mods:
            mod.delete()

    for field, value in ALCOHOL_MODS:
        if not alcohol_lite_mods.filter(field=field, value=value).exists():
            models.Mods.objects.create(
                owner=character.owner,
                character=character.name,
                field=field,
                value=value,
                source=ALCOHOL_LITE_SOURCE,
            )

def get_next_character_copy_name(character_name):
    character_name = (character_name or "").strip()
    match = re.match(r"^(.*?)(?:\s+(\d+))?$", character_name)
    if match and match.group(2):
        base_name = match.group(1).strip()
        next_number = int(match.group(2)) + 1
    else:
        base_name = character_name
        next_number = 2

    while True:
        candidate = f"{base_name} {next_number}".strip()
        if not models.Character.objects.filter(name=candidate).exists():
            return candidate
        next_number += 1

def copy_model_instance(instance, **overrides):
    data = {
        field.name: getattr(instance, field.name)
        for field in instance._meta.fields
        if field.name != "id"
    }
    data.update(overrides)
    return instance.__class__.objects.create(**data)

def redirect_to_characters(request):
    if 'character_type' in request.GET:
        query = urlencode({'character_type': request.GET.get('character_type')})
        return redirect(f'/dunnorpg?{query}')

    if 'character_type' in request.POST:
        query = urlencode({'character_type': request.POST.get('character_type')})
        return redirect(f'/dunnorpg?{query}')

    return redirect('/dunnorpg')

class charGET(ListView):
    model = models.Character
    template_name = 'home.html'
    context_object_name = 'characters'

    def get_base_queryset(self):
        if self.request.user.is_superuser:
            return self.model.objects.filter(hidden=False)
        return self.model.objects.filter(
            owner=self.request.user,
            hidden=False
        )

    def get_queryset(self):
        qs = self.get_base_queryset()

        selected_type = self.request.GET.get('character_type', 'Player')
        if selected_type:
            qs = qs.filter(type=selected_type)

        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        base_qs = self.get_base_queryset()
        base_qs = base_qs.exclude(type__isnull=True)
        selected_type = self.request.GET.get('character_type', 'Player')

        print(base_qs.values_list('type', flat=True).distinct())
        context['selected_type'] = selected_type
        context['character_types'] = sorted(base_qs.values_list('type', flat=True).distinct())
        context['characters_count'] = self.get_queryset().count()
        context['copy_default_names'] = {
            character.id: get_next_character_copy_name(character.name)
            for character in context['characters']
        }

        return context
    
class AddCharacterView(APIView):
    template_name = 'character_add.html'
    rendered_classes = [TemplateHTMLRenderer]

    def get(self,request):
        races = models.Races.objects.order_by('name')
        if not request.user.is_superuser:
            races = races.exclude(name__startswith='|', name__endswith='|')
        classes = models.Classes.objects.order_by('name')
        
        context = {
            'races': races,
            'classes': classes
        }
        return Response(context)

class DeleteCharacter(APIView):
    def get(self,request,char_id):
        character = get_object_or_404(models.Character,id=char_id)
        
        with transaction.atomic():
            models.Skills.objects.filter(owner=request.user ,character=character.name).delete()
            models.Effects.objects.filter(owner=request.user ,character=character.name).delete()
            character.delete()

        return redirect_to_characters(request)

class CopyCharacter(APIView):
    def post(self, request, char_id):
        character = get_object_or_404(models.Character, id=char_id)
        if not request.user.is_superuser and character.owner != request.user.username:
            raise Http404('Invalid character')

        new_name = (request.POST.get("name") or "").strip()
        if not new_name:
            messages.error(request, "Brak nazwy postaci")
            return redirect_to_characters(request)

        try:
            amount = int(request.POST.get("amount") or 1)
        except ValueError:
            amount = 1

        if amount < 1:
            messages.error(request, "Ilość kopii musi być większa od 0")
            return redirect_to_characters(request)

        max_name_length = models.Character._meta.get_field("name").max_length
        if len(new_name) > max_name_length:
            messages.error(request, f"Nazwa postaci może mieć maksymalnie {max_name_length} znaków")
            return redirect_to_characters(request)

        if models.Character.objects.filter(name=new_name).exists():
            messages.error(request, "Postać o takiej nazwie już istnieje")
            return redirect_to_characters(request)

        copy_names = []
        next_name = new_name
        for _ in range(amount):
            if len(next_name) > max_name_length:
                messages.error(request, f"Nazwa postaci może mieć maksymalnie {max_name_length} znaków")
                return redirect_to_characters(request)

            copy_names.append(next_name)
            next_name = get_next_character_copy_name(next_name)

        related_models = [
            models.Skills,
            models.Eq,
            models.CharItems,
            models.Effects,
            models.Mods,
        ]

        with transaction.atomic():
            copied_names = []
            for copy_name in copy_names:
                new_character = copy_model_instance(character, name=copy_name)
                copied_names.append(new_character.name)

                for related_model in related_models:
                    related_objects = related_model.objects.filter(character=character.name)
                    if any(field.name == "owner" for field in related_model._meta.fields):
                        related_objects = related_objects.filter(owner=character.owner)

                    for related_object in related_objects:
                        copy_model_instance(
                            related_object,
                            owner=new_character.owner,
                            character=new_character.name,
                        )

        messages.success(request, f"Skopiowano postać {amount} razy: {', '.join(copied_names)}")

        return redirect_to_characters(request)

class EditCharacterView(APIView):
    template_name = 'character_add_skills.html'
    rendered_classes = [TemplateHTMLRenderer]

    def get(self, request, *args, **kwargs):
        user = self.request.user
        id = kwargs['id']
        chosen_character = get_object_or_404(models.Character, id=id)
        available_skills = models.Skills_Decs.objects.filter(
            Q(restrictions__icontains='all') | Q(restrictions__icontains=chosen_character.chosen_class) | Q(restrictions__icontains='Uniwersalne')
        ).order_by('name').values()

        character_skills_queryset = models.Skills.objects.filter(
            owner=chosen_character.owner,
            character=chosen_character.name
        ).order_by('skill').values()
        
        users = []
        for user in User.objects.values():
            users.append(user)

        stats_path = Path(__file__).resolve().parent / 'json_data' / 'stats.json'
        with stats_path.open(encoding='utf-8') as stats_file:
            stats_descriptions = json.load(stats_file)

        context = {
            "character": chosen_character,
            "current_skills": character_skills_queryset,
            "available_skills": available_skills,
            "users": users,
            "stats_descriptions": stats_descriptions,
        }
        return Response(context)

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
        current_skills = []

        for skill in context['skills']:
            current_skills.append(skill['skill'])

        users = []
        for user in User.objects.values():
            users.append(user)

        context['character'] = chosen_character
        context['character_id'] = id
        context['character_stats'] = character_stats
        context['skills_count'] = skills_points
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
        current_skills = []

        for skill in character_skills:
            cost = int(models.Skills_Decs.objects.filter(name=skill['skill']).values()[0]['cost'])
            current_skills.append(skill['skill'])
            if skill['category'][1:] != 'free':
                skills_count += skill['level'] * cost
                
        skills_points = chosen_character['points_left']

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

        requirements_satisfied = True
        req_stats = []
        reqs_raw = validated_skill[f"reqs{skill_to_add.level}"] or ""
        reqs = reqs_raw.split(";") if reqs_raw else []
        for req in reqs:
            if not req:
                continue
            req_stat = req[-1]
            req_value = req[:-1]
            req_stats.append(f"{req_stat}: {req_value}")

            req_satisfied = chosen_character[req_stat] >= req_value
            if not req_satisfied:
                requirements_satisfied = False
                break

        correct = False
        if skills_points > 0 and skill_to_add.level <= skills_points:
            if requirements_satisfied:
                if validated_skill['name'] not in current_skills:
                    correct = True
                else:
                    msg = f"{validated_skill['name']} is already one of your skills."
            else:
                msg = "Requirements: " + ", ".join(req_stats)
        else:
            msg = f"Not enough points: {skills_points} points available and {skill_to_add.level} points are needed for {validated_skill['name']} lvl.{skill_to_add.level}"

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
        drunkenness_limit = get_drunkenness_limit(chosen)

        eq_items = models.Eq.objects.all().filter(character=chosen.name)
        ammo = []
        for item in eq_items:
            if "pocisk" in item.name.lower() or "strzała" in item.name.lower() or "bełt" in item.name.lower():
                ammo.append(item)
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
            skill['use_cost'] = skill_description['use_cost']
            skill['range'] = skill_description['range']
            skill['required_cel'] = skill_description['requiredCel']
            skill['dice'] = skill_description['dice']
            skill['ap'] = skill_description['ap']
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

        try:
            alcohol_level = int(chosen.alcohol)
        except (TypeError, ValueError):
            alcohol_level = 0

        types = ['Helmet','Torso','Boots','Gloves','Amulet','Other']

        eq_helmets_qs = models.Eq.objects.filter(character=chosen.name, type='Helmet').order_by('name')
        eq_torsos_qs = models.Eq.objects.filter(character=chosen.name, type='Torso').order_by('name')
        eq_gloves_qs = models.Eq.objects.filter(character=chosen.name, type='Gloves').order_by('name')
        eq_boots_qs = models.Eq.objects.filter(character=chosen.name, type='Boots').order_by('name')
        eq_amulets_qs = models.Eq.objects.filter(character=chosen.name, type='Amulet').order_by('name')
        eq_mounts_qs = models.Eq.objects.filter(character=chosen.name, type='Animal').order_by('name')
        eq_mounts_armor_qs = models.Eq.objects.filter(
            Q(type='Mount Armor') | Q(name__in=models.Items.objects.filter(category='animal_armor').values_list('name', flat=True)),
            character=chosen.name,
        ).order_by('name')
        eq_mounts_horseshoes_qs = models.Eq.objects.filter(
            character=chosen.name,
            name__in=models.Items.objects.filter(category='animal_horseshoes').values_list('name', flat=True)
        ).order_by('name')
        eq_mounts_saddles_qs = models.Eq.objects.filter(
            character=chosen.name,
            name__in=models.Items.objects.filter(category='animal_saddle').values_list('name', flat=True)
        ).order_by('name')
        eq_weapons_qs = models.Eq.objects.filter(character=chosen.name).exclude(type__in=types).order_by('name')
        
        context['helmet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Helmet').first()
        context['torso'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Torso').first()
        context['gloves'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Gloves').first()
        context['boots'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Boots').first()
        context['amulet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Amulet').first()
        context['mount'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount').first()
        context['mount_armor'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_armor').first()
        context['mount_horseshoes'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_horseshoes').first()
        context['mount_saddle'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_saddle').first()
        context['leftItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Left').first()
        context['rightItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Right').first()
        context['sideItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Side').first()
        context['chosen_character'] = [serializer.data] 
        context['mods'] = mods
        context['ammo'] = ammo
        context['skills'] = skills
        context['skillsMagical'] = skillsMagical
        context['skillsMelee'] = skillsMelee
        context['skillsRange'] = skillsRange
        context['skillsAgility'] = skillsAgility
        context['skillsOther'] = skillsOther
        context['race_desc'] = race['desc']
        context['race_id'] = race['id']

        context["class"] = chosen_class
        context['drunkenness_limit'] = drunkenness_limit
        context['alcohol_state'] = get_alcohol_state(chosen, alcohol_level, drunkenness_limit)
        context['is_over_drunkenness_limit'] = alcohol_level > drunkenness_limit
        
        context['eq_weapons'] = eq_weapons_qs
        context['eq_helmets'] = eq_helmets_qs
        context['eq_torsos'] = eq_torsos_qs
        context['eq_gloves'] = eq_gloves_qs
        context['eq_boots'] = eq_boots_qs
        context['eq_amulets'] = eq_amulets_qs
        context['eq_mounts'] = eq_mounts_qs
        context['eq_mounts_armor'] = eq_mounts_armor_qs
        context['eq_mounts_horseshoes'] = eq_mounts_horseshoes_qs
        context['eq_mounts_saddles'] = eq_mounts_saddles_qs

        return context 
    
class TakeItemDurFromAttack(APIView):
    def get(self, request, *args, **kwargs):
        item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
        if item.durability >=0:
            item.durability-=1
        item.save()
        return Response("OK")

class calculateGettingHit(APIView):
    def get(self, request, *args, **kwargs):
        dmg = kwargs['dmg']
        ap = kwargs['ap']
        parts = kwargs['parts'].split("|")
        use_multiplier = bool(kwargs['multiplier'])
        raw_dmg = int(dmg+ap)

        deadly = True
        if parts == ["head"] and use_multiplier:
            dmg = int(dmg*1.5)
        if parts in [["hands"],["legs"],["hands","legs"]]:
            deadly = False

        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        helmet = models.CharItems.objects.filter(character=char.name, position='Helmet').first()
        torso = models.CharItems.objects.filter(character=char.name, position='Torso').first()
        boots = models.CharItems.objects.filter(character=char.name, position='Boots').first()
        gloves = models.CharItems.objects.filter(character=char.name, position='Gloves').first()
        items = {
            'head': helmet,
            'torso': torso,
            'legs': boots,
            'hands': gloves
        }

        armor = 0

        if not "armor" in parts:
            for item in items:
                item = items[item]
                try:
                    desc_armor = models.Items.objects.filter(name=item.name).first().armor
                    if desc_armor != 0:
                        armor += math.ceil(item.durability / 50)
                except:
                    pass

            armor -= ap
            dmg = int(dmg*float(kwargs['final_multiplier'])) #Use additional multiplier before armor
            dmg -= armor

        injured = ""
        if dmg > 0:
            char.HP -= dmg
            if char.HP <= 0:
                if deadly:
                    char.HP = 0
                else:
                    char.HP = 1 #Attacks on hand/leg cannot kill directly
                injured = " oraz stajesz się nieprzytomny/a. Zaczynasz się wykrwawiać"
            char.save()

        destroyed = False
        d_count = 0

        if not "armor" in parts:
            for part in parts:
                items[part].durability-=(raw_dmg)
                if items[part].durability < 0:
                    items[part].durability = 0
                    destroyed = True
                    d_count += 1
                items[part].save()

        destroyed_txt = ""
        if destroyed:
            destroyed_txt = f"Krytycznie uszkodzono {d_count} elementów pancerza."

        if dmg > 0: 
            messages.error(request, f"Uderzenie przebiło pancerz! Tracisz {dmg} życia{injured}. {destroyed_txt}")
        else:
            messages.success(request, "Uderzenie zatrzymało się na pancerzu!")
        return redirect(f"/dunnorpg/character_detail/{kwargs['char_id']}")

class TakeAmmoFromAttack(APIView):
    def get(self, request, *args, **kwargs):
        item = get_object_or_404(models.Eq, id=kwargs['item_id'])
        item.amount-=int(kwargs['item_amount'])
        if item.amount > 0:
            item.save()
        else:
            item.delete()
        return Response("OK")

class MoveItemToEq(APIView):
    def get(self, request, *args, **kwargs):
        item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
        
        char = get_object_or_404(models.Character, name=item.character)
        
        eq_weight = get_character_current_weight(char)
            
        max_weight = get_character_max_weight(char)
        if eq_weight <= max_weight:
            if item.position == "Mount":
                for attachment in models.CharItems.objects.filter(character=char.name, position__in=MOUNT_ATTACHMENT_POSITIONS):
                    move_char_item_to_eq(attachment)

            move_char_item_to_eq(item)
        else:
            messages.error(request, f"Not enough space in {char.name}'s equipment for '{item.name}' ({eq_weight}/{max_weight}kg)")

        return redirect(f"/dunnorpg/character_detail/{kwargs['char_id']}")

class UpgradeCharacterStats(APIView):
    def get(self, request, *args, **kwargs):
        char_id = kwargs['char_id']
        stat = kwargs['stat']
        if stat not in {'INT', 'SIŁ', 'ZRE', 'CHAR', 'CEL', 'SPO'}:
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
        if stat not in {'INT', 'SIŁ', 'ZRE', 'CHAR', 'CEL', 'SPO'}:
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
        restrictions = []
        
        for skill in skills:
            skill_restrictions = skill.restrictions.split(';')
            for rst in skill_restrictions:
                if rst == "all":
                    rst = "Uniwersalne"
                if rst not in restrictions:
                    restrictions.append(rst)
        

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
        other_skills = list(skills.filter(category='Inne').values().order_by('name'))
        current_user = request.user

        for x in range(len(magical_skills)):
            magical_skills[x]["number"] = x+1

        combined_other_skills = drinking_skills+charisma_skills+command_skills+horsemanship_skills+aliigment_skills+crafting_skills+other_skills
        context = {
            'magical_skills': magical_skills,
            'melee_skills': melee_skills,
            'range_skills': range_skills,
            'agility_skills': agility_skills,
            'education_skills': education_skills,
            'animals_skills': animals_skills,
            'eq_skills': eq_skills,
            'other_skills': combined_other_skills,
            'all_skills': skills,
            'restrictions': restrictions,
            'skills': ['Magia','Zwarcie','Dystansowe','Zwinność','Edukacja','Natura','Ekwipunek','Inne', 'Wszystkie'],
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
                nr = data[-1]
                needs = []
                reqs_raw = serializer.data[f"reqs{nr}"]
                if reqs_raw is None:
                    reqs_raw = ""
                reqs = reqs_raw.split(";")

                for req in reqs:
                    if req != "":
                        stat = req[:-1]
                        val = req[-1]
                        needs.append(f"{stat}: {val}")

                lvl_uses = serializer.data[f"useslvl{nr}"]

                levels.append({
                    'level': data, 
                    'desc': serializer.data[data], 
                    'needs': needs, 
                    'uses': lvl_uses
                    })

        context = {
            'skill': serializer.data,
            'levels': levels,
            'user': current_user
        }

        return Response(context)

def skill_add(request,char_id,skill_id,lvl):
    character = get_object_or_404(models.Character, id=char_id)
    skill_details = get_object_or_404(models.Skills_Decs, id=skill_id)
    lvl = int(lvl)

    while not getattr(skill_details, f"level{lvl}"):
        lvl -= 1

    reqOK = True
    reqs_raw = getattr(skill_details, f"reqs{lvl}", "") or ""
    reqs = reqs_raw.split(";") if reqs_raw else []

    for req in reqs:
        stat = req[:-1]
        char_stat = int(getattr(character, stat))
        value = req[-1:]
        if char_stat < int(value):
            messages.error(request, f"Halo, halo! Za mało {stat}! Potrzeba {value} a jest {char_stat}!")
            reqOK = False


    if reqOK:
        already_has_skill = models.Skills.objects.filter(
            owner=character.owner,
            character=character.name,
            skill=skill_details.name
        ).exists()
        if already_has_skill:
            messages.error(request, "Już posiadasz tę umiejętność")
            reqOK = False

    if reqOK:
        skill_cost = lvl * int(skill_details.cost)
        if int(character.points_left) < skill_cost:
            messages.error(request, f'Brak wolnych punkcików. Potrzeba {skill_cost} a ty masz {character.points_left}. We se najpierw trochę zdobądź a potem zawracaj mi interes.')
            reqOK = False

    if reqOK:
        models.Skills.objects.create(
            owner = character.owner,
            character = character.name,
            skill = skill_details.name,
            category = skill_details.category,
            level = lvl,
            desc = getattr(skill_details, f"level{lvl}"),
            uses_left = getattr(skill_details, f"useslvl{lvl}", None) or 0
        )

        character.points_left -= skill_cost
        character.save()

    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
    

def enter_or_leave_fight(request,char_id):
    character = get_object_or_404(models.Character, id=char_id)
    if character.inFight:
        character.inFight = False
        character.actionLeft = 1.0
        character.counter = 0
        character.counter2 = 0
    else:
        character.inFight = True
    character.save()
    return redirect(f'/dunnorpg/character_detail/{char_id}/')

def skill_delete(request,char_id,skill_id):
    skill = get_object_or_404(models.Skills, id=skill_id)
    skill_details = get_object_or_404(models.Skills_Decs, name=skill.skill)
    character = get_object_or_404(models.Character, id=char_id)

    if skill.source == "natural_free":
        messages.error(request, f'{skill.skill} jest darmową umiejętnością z rasy lub klasy i nie można jej usunąć.')
        return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
    
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
        reqs_ok = True
        reqs_text = skill_details[f"reqs{skill.level+1}"]
        reqs = reqs_text.split(";") if reqs_text else []

        for req in reqs:
            reqs_ok = (req==None) or (int(character[f"{req[:-1]}"])>=int(req[-1]))
            if not reqs_ok:
                break

        if reqs_ok:
            cat = skill_details['category']
            points_ok = character_object.points_left>0
               
            if points_ok:        
                skill.level += 1
                skill.desc = skill_details['desc']+' '+skill_details[f"level{skill.level}"]
                skill.uses_left = skill_details[f"useslvl{skill.level}"] or 0
                skill.save()

                character_object.points_left -= int(skill_details['cost'])
                character_object.save()
            else:
                messages.error(request, f'Za mało punktów, żeby ulepszyć {skill.skill}.')
        else:
            msg = f"Nie spełniasz wymagań do ulepszenia {skill.skill}!"
            messages.error(request, msg)
    else:
        messages.error(request,f'{skill.skill}: Osiagnięto już maksymalny poziom!')
    
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
        skill.uses_left = skill_details[f"useslvl{skill.level}"] or 0
        skill.save()
        
        if skill_details['category'] != 'Magical':
            character_object.points_left += int(skill_details['cost'])
        character_object.save()
    else:
        messages.error(request,f'{skill.skill}: Niżej się nie da!')
    
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
def create_character(request,name,char_class,race,type,owner,exp):
    try:
        if not name.strip():
            messages.error(request, "Brak nazwy postaci")
            return redirect('character_add')

        race =  get_object_or_404(models.Races, name=race)
        maxHP = race.hp
        size_dict = {"S": 0.5,"M": 1,"L": 2}
        race = get_object_or_404(models.Races, name=race)
        char_class = get_object_or_404(models.Classes, name=char_class)
        class_mods = char_class.mods.split(";")
        class_hp_mod = int(char_class.hp_mod or 0)
        class_skills = [skill for skill in char_class.skills.split(";") if skill]
        race_skills = [skill for skill in race.Skills.split(";") if skill]
        class_effects = char_class.effects.split(";")
        class_mods = char_class.mods.split(";")
        counter_name = CLASS_COUNTERS.get(char_class.name, "")

        if type=="":
            type="Player"
        if owner=="":
            owner=request.user

        if models.Character.objects.filter(name=name).exists():
            messages.error(request, "Nazwa zajęta")
            return redirect('character_add')
        elif race=="" or char_class=="":
            messages.error(request, f"Nie wybrano rasy lub klasy")
            return redirect('character_add')

        raceStatsPlus = race.statPlus.split(";")
        raceStatsMinus = race.statMinus.split(";")

        classStats = {"INT":0,"SIŁ":0,"CHAR":0,"ZRE":0,"CEL":0, "SPO": 0}
        for mod in class_mods:
            if mod != '':
                mod_val = int(mod[-2:])
                if mod.startswith("CHAR"):
                    classStats['CHAR'] += mod_val
                else:
                    classStats[mod[:-2]] = mod_val

        models.Character.objects.create(
            owner=owner,
            name=name,
            type=type,
            exp=exp,
            chosen_class=char_class,
            race=race,
            size=size_dict[race.size],
            HP=maxHP+class_hp_mod,
            fullHP=maxHP+class_hp_mod,
            coins=0,
            INT=0+int(raceStatsPlus[0])-int(raceStatsMinus[0])+classStats['INT'],
            SIŁ=0+int(raceStatsPlus[1])-int(raceStatsMinus[1])+classStats['SIŁ'],
            ZRE=0+int(raceStatsPlus[2])-int(raceStatsMinus[2])+classStats['ZRE'],
            CHAR=0+int(raceStatsPlus[3])-int(raceStatsMinus[3])+classStats['CHAR'],
            CEL=0+int(raceStatsPlus[4])-int(raceStatsMinus[4])+classStats['CEL'],
            SPO=0+int(raceStatsPlus[5])-int(raceStatsMinus[5])+classStats['SPO'],
            points_left=race.points_limit,
            weaponBonus=race.weaponsBonus,
            preferredWeapons=race.weaponsPreffered,
            extra_capacity=0,
            counterName=counter_name,
            mutation = "-"
        )

        for skill in class_skills:
            grant_free_skill(owner, name, skill)

        for skill in race_skills:
            grant_free_skill(owner, name, skill)

        for effect in class_effects: #Effects are to be overhauled
            eff_name = effect[:-2]
            parts = effect.split("-")
            eff_nr = parts[len(parts)-1]
            #eff_desc = models.get_object_or_404(models.Effects_Decs, name=eff_name)
            models.Effects.objects.create(
                owner = owner,
                character = name,
                name = eff_name,
                time = 1 #TODO: Handle when effects changing part starts
            )

        try:
            new_char = get_object_or_404(models.Character, name=name)
            return redirect(f'character_add_skills', new_char.id)
        except Exception as e:
            messages.error(request, f"Wystąpił błąd [404]: {e}")
            return redirect(f'character_add')
    except Exception as e:
        messages.error(request, f"Wystąpił błąd: {e}")
        print(traceback.format_exc())
        return redirect(f'character_add')

def missing_character_name(request):
    messages.error(request, "Brak nazwy postaci")
    return redirect('character_add')

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
    if item.amount <= int(kwargs['amount']):
        item.delete()
    else:
        item.amount -= int(kwargs['amount'])
        item.weight -= itemDesc.weight*int(kwargs['amount'])
        item.save()
    return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")
def sell_item(request, **kwargs):
    try:
        city = get_object_or_404(models.Cities, visiting=True)
        eqItem = get_object_or_404(models.Eq, id=kwargs['item_id'])
        itemDesc = get_object_or_404(models.Items, name=eqItem.name)
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        amount = int(kwargs['amount'])
        
        if amount>eqItem.amount:
            messages.error(request, f"Hola, hola! Nie masz tego tyle! Masz {eqItem.amount} sztuk tego przedmiotu. ({itemDesc.name})")
            return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

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

        raw_base_price = itemDesc.price*durability_percent*amount
        base_price = float("{:.1f}".format(raw_base_price)) # e.g. 10.1

        raw_char_bonus = round(((charisma*4)*base_price)/100)
        char_bonus = float("{:.1f}".format(raw_char_bonus))

        price = base_price + char_bonus #Get 100% of calculated price + [charisma*4]% bonus

        char.coins += price
        char.save()

        eqItem.amount -= amount
        if eqItem.amount==0:
            eqItem.delete()
        else:
            eqItem.save()

        messages.success(request, f"Sprzedano {amount}x {itemDesc.name} za {price} monet! Obecny majątek: {char.coins} monet.")
    except:
        messages.error(request, f"Gdzie chcesz to sprzedać? Najpierw zajrzyj z drużyną do jakiegoś miasta!")
    return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")
def give_item(request, **kwargs):
    from_char = get_object_or_404(models.Character, id=kwargs['from_char'])
    to_char = get_object_or_404(models.Character, id=kwargs['to_char'])
    given_amount = kwargs['amount']
    if (to_char.type or "").lower() != "player" and not request.user.is_superuser:
        messages.error(request, f"Cannot transfer to {to_char.name}.")
        return redirect(f"/dunnorpg/items/ch{from_char.id}")
    if kwargs["item_id"]!=0:
        eq_item = get_object_or_404(models.Eq, id=kwargs['item_id'])
        itemDesc = get_object_or_404(models.Items, name=eq_item.name)
        if itemDesc.unobtainable and not request.user.is_superuser:
            messages.error(request, f"{eq_item.name} nie moze zostac przekazane.")
            return redirect(f"/dunnorpg/items/ch{from_char.id}")

        if given_amount <= eq_item.amount:
            max_weight = get_character_max_weight(to_char)
            current_weight = get_character_current_weight(to_char)

            if itemDesc.weight * given_amount + current_weight <= max_weight:
                models.Eq.objects.create(
                    owner=to_char.owner,
                    character=to_char.name,
                    name=eq_item.name,
                    type=eq_item.type,
                    weight=eq_item.weight*given_amount,
                    durability=eq_item.durability,
                    amount=given_amount,
                    additional_description=eq_item.additional_description,
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
            messages.error(request, "Nothing to swap with!") #TODO: Instead of message error we are to create new item at char_items
            return redirect('character_detail', char.id)
        left = True
    else:
        try:
            to_swap = get_object_or_404(models.CharItems, character=char.name, hand="Right")
        except:
            messages.error(request, "Nothing to swap with!") #TODO: Instead of message error we are to create new item at char_items
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
                amount = 1,
                additional_description = rightItem.additional_description
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
    dur = request.POST.get('dur')
    if dur is not None and dur != '':
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
def change_char_details(request, **kwargs):
    try:
        data = json.loads(request.body)
        char = get_object_or_404(models.Character, id=kwargs['char_id'])

        char.fullHP = int(data['maxHP'])
        char.barrier = int(data['barrier'])
        char.points_left = int(data['points'])
        char.type = (data.get('type') or 'Player').strip() or 'Player'
        char.model_url = data['url']
        char.size = f"{float(data['size']):g}"
        char.save()

        return JsonResponse({"message": "Pomyślnie zmieniono dane"}, status=200)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=400)
    
def end_round_infight(request, **kwargs):
    try:
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        effects = models.Effects.objects.filter(character=char.name)
        removedAny = False

        char.actionLeft = 1.0
        char.save()

        for effect in effects:
            if effect.time == 1:
                effect.delete()
                removedAny = True
            elif effect.time < 100:
                effect.time -= 1
                effect.save()

        if removedAny:
            msg = "Zakończono rundę, odnowiono ilość akcji postaci oraz usunięto niektóre efekty"
        else:
            msg = "Zakończono rundę oraz odnowiono ilość akcji postaci"

        messages.success(request, msg)
        return redirect('character_detail', char.id) 
    except Exception as e:
        print(traceback.format_exc())
        messages.success(request, f"Błąd: {e}")
        return redirect('character_detail', char.id) 

def change_coins(request, **kwargs):
    if request.method == 'POST':
        try:
            char = get_object_or_404(models.Character, id=kwargs['char_id'])
            coins_raw = request.POST['coins-amount'].strip().replace(',', '.')
            if not re.match(r'^\d+(\.\d)?$', coins_raw):
                raise ValueError("Monety mogą mieć maksymalnie jedno miejsce po przecinku")

            coins = float(coins_raw)
            if coins < 0:
                raise ValueError("Monety nie mogą być mniejsze niż 0")

            char.coins = coins
            char.save()

            coins_display = f"{char.coins:g}"
            msg = f"Pomyślnie zmieniono Monety na {coins_display}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"message": msg, "coins": coins_display}, status=200)

            messages.success(request, msg)
            return redirect('character_detail', char.id)
        except Exception as e:
            msg = f"Błąd zmiany Monet: {e}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)

            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])
    
def change_action_amount(request, **kwargs):
    if request.method == 'POST':
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        print(request.POST)
        char.actionLeft = float(request.POST['actions-amount'])
        char.save()
        return redirect('character_detail', char.id) 

def change_counter(request, **kwargs):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    counter_field = kwargs.get('counter_field')
    fields = {
        "counter": ("counter", "counterName"),
        "counter2": ("counter2", "counterName2"),
    }

    if counter_field not in fields:
        return JsonResponse({"error": "Nieprawidłowy licznik."}, status=400)

    try:
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        value_raw = request.POST.get(counter_field, '').strip()
        if not re.match(r'^\d+$', value_raw):
            raise ValueError("Licznik musi być liczbą całkowitą większą lub równą 0")

        value = int(value_raw)
        value_field, name_field = fields[counter_field]
        counter_name = getattr(char, name_field) or "Licznik"
        setattr(char, value_field, value)
        char.save()

        msg = f"Pomyślnie zmieniono {counter_name} na {value}"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"message": msg, "counter_field": counter_field, "value": value}, status=200)

        messages.success(request, msg)
        return redirect('character_detail', char.id)
    except Exception as e:
        msg = f"Błąd zmiany licznika: {e}"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"error": msg}, status=400)

        messages.error(request, msg)
        return redirect('character_detail', kwargs['char_id'])

def change_health(request, **kwargs):  
    if request.method == 'POST':
        try:
            char = get_object_or_404(models.Character, id=kwargs['char_id'])
            char.HP = int(request.POST['hp'])
            char.save()

            msg = f"Pomyślnie zmieniono Życie na {char.HP}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"message": msg, "hp": char.HP}, status=200)

            messages.success(request, msg)
            return redirect('character_detail', char.id)
        except Exception as e:
            msg = f"Błąd zmiany Życia: {e}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)

            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])

def change_barrier(request, **kwargs):
    if request.method == 'POST':
        try:
            char = get_object_or_404(models.Character, id=kwargs['char_id'])
            barrier = int(request.POST['barrier'])
            if barrier < 0:
                raise ValueError("Bariera nie może być mniejsza niż 0")

            char.barrier = barrier
            char.save()

            msg = f"Pomyślnie zmieniono Barierę na {char.barrier}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"message": msg, "barrier": char.barrier}, status=200)

            messages.success(request, msg)
            return redirect('character_detail', char.id)
        except Exception as e:
            msg = f"Błąd zmiany Bariery: {e}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)

            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])

def change_food_water(request, **kwargs):
    if request.method == 'POST':
        try:
            translate_stat = {
                "food": "Nasycenie",
                "water": "Nawodnienie",
                "alcohol": "Alkohol",
            }

            stat_type = kwargs['stat_type']
            if stat_type not in ["food", "water", "alcohol"]:
                raise Http404("Invalid food/water stat")

            char = get_object_or_404(models.Character, id=kwargs['char_id'])
            value = int(request.POST[f'{stat_type}-amount'])
            msg = ""
            msg_type = "success"

            if stat_type == "alcohol":
                previous_alcohol_level = char.alcohol
                value = max(0, value)
                char.alcohol = value
            else:
                value = max(0, min(100, value))
                current_value = getattr(char, stat_type)
                char, msg = manageFoodAndWater(char, value - current_value, stat_type)
            char.save()
            if stat_type == "alcohol":
                sync_alcohol_mods(char, previous_alcohol_level)

            if msg != "":
                msg_type = "error"
                final_msg = msg
            elif stat_type == "alcohol":
                drunkenness_limit = get_drunkenness_limit(char)
                if value > drunkenness_limit:
                    msg_type = "error"
                    final_msg = "Jesteś pijany!"
                elif value > 0:
                    msg_type = "warning"
                    final_msg = "Odczuwasz upojenie alkoholem"
                else:
                    final_msg = f"Pomyślnie zmieniono wartość {translate_stat[stat_type]} na {value}"
            else:
                final_msg = f"Pomyślnie zmieniono wartość {translate_stat[stat_type]} na {getattr(char, stat_type)}%"

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                extra_data = {}
                if stat_type == "alcohol":
                    extra_data = {
                        "drunkenness_limit": get_drunkenness_limit(char),
                        "alcohol_state": get_alcohol_state(char),
                    }
                return JsonResponse({
                    "message": final_msg,
                    "message_type": msg_type,
                    "stat_type": stat_type,
                    "value": getattr(char, stat_type),
                    "hp": char.HP,
                    **extra_data,
                }, status=200)

            if msg_type == "error":
                messages.error(request, final_msg)
            elif msg_type == "warning":
                messages.warning(request, final_msg)
            else:
                messages.success(request, final_msg)

            return redirect('character_detail', char.id)
        except Exception as e:
            msg = f"Błąd zmiany wartości: {e}"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)

            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])

def manageExp(char, exp):
    msg = ''
    msg_type = 'success'
    waterMessage = ""
    foodMessage = ""
    try:
        try:
            amount = int(exp)
        except:
            amount = 0
        added_amount = int(char.exp) + amount

        if added_amount >= 100:
            lvls_to_add = int(added_amount/100)
            char.exp = added_amount - (lvls_to_add*100)
            char.level += lvls_to_add
            char.points_left += lvls_to_add
            char, waterMessage = manageFoodAndWater(char, -20*lvls_to_add, "water")
            char, foodMessage = manageFoodAndWater(char, -20*lvls_to_add, "food")
            msg = f"Zdobyto poziom! Nowy poziom to {char.level}, otrzymano {lvls_to_add} punktów umiejętności."
            if waterMessage != "":
                msg += f" {waterMessage}"
            if foodMessage != "":
                msg += f" {foodMessage}"
        else:
            if added_amount < 0:
                added_amount = 0
            char.exp = added_amount
            if amount >= 0:
                msg = f"Dodano {amount} doświadczenia, łącznie masz już {added_amount}% doświadczenia"
            else:
                msg = f"Zabrano {abs(amount)} doświadczenia, pozostało ci {added_amount}% doświadczenia"

        char.save()

    except Exception as e:
        msg = f"Błąd: {e}"
        msg_type = 'error'
        print(traceback.format_exc())

    return char, msg, msg_type

def add_exp(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    msg = ''
    msg_type = ''

    char, msg, msg_type = manageExp(char, kwargs['exp'])

    if msg_type == 'error':
        messages.error(request, msg)
    else:
        messages.success(request, msg)

    return redirect('character_detail', char.id)

def char_wear_item(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    char_skills = models.Skills.objects.filter(character=char.name)
    place = kwargs['place'] #hand or position
    item_id = kwargs['item_id']
    item_eq_obj = models.Eq.objects.get(character=char.name,id=item_id)
    item = models.Items.objects.get(name=item_eq_obj.name)
    item_category = (item.category or "").lower()

    if place in MOUNT_ATTACHMENT_POSITIONS:
        if not models.CharItems.objects.filter(character=char.name, position="Mount").exists():
            messages.error(request, "Najpierw załóż wierzchowca.")
            return redirect('character_detail', char.id)

        allowed_categories = MOUNT_ATTACHMENT_CATEGORIES.get(place, set())
        if item_category not in allowed_categories and not (place == "Mount_armor" and item.type == "Mount Armor"):
            messages.error(request, "Ten przedmiot nie pasuje do wybranego slotu wierzchowca.")
            return redirect('character_detail', char.id)

    if place == "Mount" and item.type != "Animal":
        messages.error(request, "W tym slocie można założyć tylko wierzchowca.")
        return redirect('character_detail', char.id)

    can_wear_armor, armor_weight_message = can_character_wear_armor_weight(char, item, place)
    if not can_wear_armor:
        messages.error(request, armor_weight_message)
        return redirect('character_detail', char.id)
    
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
            leftItemDesc = get_object_or_404(models.Items, name=leftItem.name) if leftItem else None
            if leftItemDesc and leftItemDesc.dualHanded:
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
                position = '',
                additional_description = item_eq_obj.additional_description
                )
        else:
            models.CharItems.objects.create(
                owner = request.user,
                character = char.name,
                name = item.name,
                durability = item_eq_obj.durability,
                hand = '',
                position = place.capitalize(),
                additional_description = item_eq_obj.additional_description
                )            
    else:
        charItObj.name = item.name
        charItObj.durability = item_eq_obj.durability
        charItObj.additional_description = item_eq_obj.additional_description
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
                    time = effect[2]
                )
            else:
                curr_effect.time = 100
                curr_effect.save()

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

def change_skill_uses(request, **kwargs):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        skill = get_object_or_404(
            models.Skills,
            id=kwargs['skill_id'],
            owner=char.owner,
            character=char.name,
        )
        skill_desc = get_object_or_404(models.Skills_Decs, name=skill.skill)
        max_uses = getattr(skill_desc, f"useslvl{skill.level}", None)
        if max_uses is None:
            raise ValueError("Ta umiejętność nie ma limitu użyć")

        uses_left = int(request.POST['uses-left'])
        if uses_left < 0:
            raise ValueError("Liczba użyć nie może być mniejsza niż 0")
        if max_uses != 1000 and uses_left > max_uses:
            raise ValueError(f"Liczba użyć nie może być większa niż {max_uses}")

        skill.uses_left = uses_left
        skill.save()
        msg = f"Pomyślnie zmieniono liczbę użyć {skill.skill} na {uses_left}"

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"message": msg, "uses_left": uses_left}, status=200)

        messages.success(request, msg)
        return redirect('character_detail', char.id)
    except Exception as e:
        msg = f"Błąd zmiany liczby użyć: {e}"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"error": msg}, status=400)

        messages.error(request, msg)
        return redirect('character_detail', kwargs['char_id'])

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

    armor_place = it1.position or it1.hand
    if armor_place in MOUNT_ATTACHMENT_POSITIONS:
        if not models.CharItems.objects.filter(character=char.name, position="Mount").exists():
            messages.error(request, "Najpierw załóż wierzchowca.")
            return redirect('character_detail', char.id)

        allowed_categories = MOUNT_ATTACHMENT_CATEGORIES.get(armor_place, set())
        if (it2D.category or "").lower() not in allowed_categories and not (armor_place == "Mount_armor" and it2D.type == "Mount Armor"):
            messages.error(request, "Ten przedmiot nie pasuje do wybranego slotu wierzchowca.")
            return redirect('character_detail', char.id)

    can_wear_armor, armor_weight_message = can_character_wear_armor_weight(char, it2D, armor_place)
    if not can_wear_armor:
        messages.error(request, armor_weight_message)
        return redirect('character_detail', char.id)

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

    max_weight = get_character_max_weight(char)
    current_weight = get_character_current_weight(char)

    if current_weight > max_weight:
        messages.error(request, f'Not enough space in equipment for {it2D.name}, {current_weight-max_weight}kg too heavy :(')
        return redirect('character_detail', char.id)

    models.Eq.objects.create(
        owner=char.owner,
        character=char.name,
        name=it1.name,
        type=it1D.type,
        weight=it1D.weight,
        durability=it1.durability,
        additional_description=it1.additional_description,
    )

    if it1D.skillEffects != None:
        for effect in it1D.skillEffects.split(';'):
            effect = effect.split("-")
            models.Effects.objects.filter(character=char.name, name=effect[0]).first().delete()
    
    it1.name = it2.name
    it1.durability = it2.durability
    it1.additional_description = it2.additional_description
    it1.save()

    if it2D.skillEffects != None:
        for effect in it2D.skillEffects.split(';'):
            effect = effect.split("-")

            models.Effects.objects.create(
                owner = char.owner,
                character=char.name,
                name = effect[0],
                time = effect[2]
            )    
    
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

def manageAdvantages(char, addOrRemove, type, info, time):
    type = type.capitalize()
    effects = models.Effects.objects.filter(character=char.name)
    countAdvs = 0
    countDisAdvs = 0
    countBigAdvs = 0
    countBigDisAdvs = 0
    remCount = 0

    if addOrRemove == "remove":
        for effect in effects:
            if effect.name == type and effect.desc == info:
                    effect.delete()
                    remCount += 1
                    break
    else:
        for effect in effects:
            if effect.name == "Przewaga":
                countAdvs += 1
            elif effect.name == "Utrudnienie":
                countDisAdvs += 1
            elif effect.name == "DużaPrzewaga":
                countBigAdvs += 1
            elif effect.name == "DużeUtrudnienie":
                countBigDisAdvs += 1

    if addOrRemove == "add":
        if type in ["Przewaga","DużaPrzewaga"]:
            if countBigAdvs >= maxBigAdvs:
                return "Failed: Aktywna już jest DużaPrzewaga"
            if type=="Przewaga":
                if countAdvs >= maxAdvs:
                    return "Failed: Osiagnięto maksymalną ilość Przewag"
        else:
            if countBigDisAdvs >= maxBigAdvs:
                return "DużeUtrudnienie jest już aktywne"
            if type=="Utrudnienie":
                if countDisAdvs >= maxAdvs:
                    return "Failed: Osiagnięto maksymalną ilość Utrudnień"
        models.Effects.objects.create(
            owner = char.owner,
            character = char.name,
            name = type,
            desc = info,
            time = time,
            category = "Aktywny"
        )
        return f"Success: Dodano {type}"
    else:
        if remCount == 0:
            return f"Failed: Nie znaleziono lub nie udało się usunąć"
        return f"Success: Removed {info}"

def manageFoodAndWater(char, value, stat_type):  # stat_type: "food" or "water"
    effects = models.Effects.objects.filter(character=char.name)
    has_food_effect = effects.filter(desc="Odczuwasz Głód", character=char.name).exists()
    has_water_effect = effects.filter(desc="Odczuwasz Pragnienie", character=char.name).exists()
    value_now = getattr(char, stat_type)
    value_changed = value_now + value
    msg = ""

    typeDict = {"food": "Głód", "water": "Pragnienie"}
    effectExists = {"food": has_food_effect, "water": has_water_effect}

    if value_changed < 0:
        diff = abs(value_changed)
        setattr(char, stat_type, 0)
        char.HP -= diff
        if char.HP <= 0:
            char.HP = 0
        msg = f"Odczuwasz {typeDict[stat_type]} i tracisz {diff} PŻ"
        if not effectExists[stat_type]:
            manageAdvantages(char, "add", "Utrudnienie", f"Odczuwasz {typeDict[stat_type]}", 1000)
    elif value_changed <= 20:
        setattr(char, stat_type, value_changed)
        msg = f"Odczuwasz {typeDict[stat_type]}"
        if not effectExists[stat_type]:
            manageAdvantages(char, "add", "Utrudnienie", f"Odczuwasz {typeDict[stat_type]}", 1000)
    else:
        if value_changed > 100:
            setattr(char, stat_type, 100)
        else:
            setattr(char, stat_type, value_changed)

        if value_changed > 20 and value_now <= 20:
            manageAdvantages(char, "remove", "Utrudnienie", f"Odczuwasz {typeDict[stat_type]}", 1000)

    return char, msg


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

            def add_character_item(item_desc, durability, amount=1, eq_id=None, char_item_id=None, equipped=False):
                item_data = {
                    'id': item_desc.id,
                    'eq_id': eq_id,
                    'char_item_id': char_item_id,
                    'rarity': item_desc.rarity,
                    'found': item_desc.found,
                    'name': item_desc.name,
                    'dur': durability,
                    'amount': amount,
                    'max_dur': item_desc.maxDurability,
                    'type': item_desc.type,
                    'price': item_desc.price,
                    'on_use': item_desc.on_use,
                    'use_cost': item_desc.use_cost,
                    'use_info': item_desc.use_info,
                    'equipped': equipped,
                }
                queryset.append(item_data)

                category_data = item_desc.__dict__ | {
                    'dur': durability,
                    'amount': amount,
                    'max_dur': item_desc.maxDurability,
                    'eq_id': eq_id,
                    'char_item_id': char_item_id,
                    'equipped': equipped,
                }
                armor_category = {
                    'helmet': 'helmet',
                    'torso': 'torso',
                    'boots': 'boots',
                    'gloves': 'gloves',
                    'amulet': 'amulets',
                    'other': 'other',
                }.get(item_desc.type.lower())
                if armor_category:
                    self.armor_dict[armor_category].append(category_data)
                else:
                    if item_desc.type == 'Animal' or item_desc.type == 'Mount Armor' or (item_desc.category or "").lower() in MOUNT_ITEM_CATEGORIES:
                        self.animals.append(category_data)
                    elif item_desc.dualHanded == False:
                        self.singlehand.append(category_data)
                    else:
                        self.twohand.append(category_data)

            for item in models.Eq.objects.filter(character=self.character.name):
                item_obj = get_object_or_404(models.Items, name=item.name)
                add_character_item(item_obj, item.durability, item.amount, item.id)

            for item in models.CharItems.objects.filter(character=self.character.name):
                if item.name:
                    item_obj = get_object_or_404(models.Items, name=item.name)
                    add_character_item(item_obj, item.durability, char_item_id=item.id, equipped=True)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        names = ['items_helmet','items_torso','items_boots','items_gloves','items_amulets','items_other']
        types = ['Helmet','Torso','Boots','Gloves','Amulet','Other']
        
        if self.character == None:
            if self.request.user.is_superuser:
                context['items_singlehand'] = models.Items.objects.filter(dualHanded=False).order_by('rarity').exclude(type__in=types)
                context['items_twohand'] = models.Items.objects.filter(dualHanded=True).order_by('rarity')   
                context['animals'] =  models.Items.objects.filter(
                    Q(type='Animal') | Q(type='Mount Armor') | Q(category__in=MOUNT_ITEM_CATEGORIES)
                ).order_by('rarity')
            else:
                context['items_singlehand'] = models.Items.objects.filter(dualHanded=False, found=True).order_by('rarity').exclude(type__in=types)
                context['items_twohand'] = models.Items.objects.filter(dualHanded=True, found=True) .order_by('rarity')
                context['animals'] =  models.Items.objects.filter(
                    Q(type='Animal') | Q(type='Mount Armor') | Q(category__in=MOUNT_ITEM_CATEGORIES),
                    found=True
                ).order_by('rarity')
            
            for x in range(len(names)):
                if self.request.user.is_superuser:
                    context[names[x]] = models.Items.objects.filter(type=types[x]).order_by('rarity')
                else:
                    context[names[x]] = models.Items.objects.filter(type=types[x], found=True).order_by('rarity')
        else:
            
            items_weight = get_character_current_weight(self.character)
            max_weight = get_character_max_weight(self.character)
            
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
            context['all_items'] = models.Items.objects.order_by('name')
            player_items = models.Eq.objects.filter(character=self.character.name)
            if not self.request.user.is_superuser:
                unobtainable_item_names = models.Items.objects.filter(unobtainable=True).values_list('name', flat=True)
                player_items = player_items.exclude(name__in=unobtainable_item_names)
            context['player_items'] = player_items.values()
            context['characters'] = models.Character.objects.filter(hidden=False, type__iexact='Player').values()
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
        additional_description = ''
        ref = self.request.GET.get('ref', '')

        try:
            ref_type, ref_id = ref.split(';', 1)
            if ref_type == 'eq':
                referenced_item = models.Eq.objects.filter(id=ref_id, name=item.name).first()
            elif ref_type == 'char':
                referenced_item = models.CharItems.objects.filter(id=ref_id, name=item.name).first()
            else:
                referenced_item = None

            if referenced_item:
                additional_description = referenced_item.additional_description
        except ValueError:
            pass

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
        context['additional_description'] = additional_description

        return context

class useItem(APIView):
    def get(self, request, *args, **kwargs):
        try:
            item_id = kwargs['id']
            item = get_object_or_404(models.Items, id=item_id)
            action = item.on_use
            actions = [part.strip() for part in action.split(";") if part.strip()]
            cost = float(item.use_cost)

            char_id = kwargs['char_id']
            char = get_object_or_404(models.Character, id=char_id)
            eq_item = models.Eq.objects.filter(name=item.name, character=char.name).first()

            if not char.inFight:
                cost = 0.0

            if float(char.actionLeft) < cost and char.inFight:
                messages.error(request,f'Nie posiadasz wystarczająco akcji! Wymagane {cost} a dostępne {char.actionLeft}.')
                return redirect(f'/dunnorpg/items/ch{char_id}')

            char, effect_messages = apply_item_use_effects(char, actions, cost, manageFoodAndWater, sync_alcohol_mods)
            for effect_message in effect_messages:
                getattr(messages, effect_message.level)(request, effect_message.text)

            if char.inFight:
                char.actionLeft -= cost

            action_names = [single_action.split("-", 1)[0] for single_action in actions]
            waterMsg = ""
            foodMsg = ""
            if not any(action_name.startswith("addWater") for action_name in action_names):
                char, waterMsg = manageFoodAndWater(char, -1, "water")
            if not any(action_name.startswith("addFood") for action_name in action_names):
                char, foodMsg = manageFoodAndWater(char, -1, "food")
            char.save()

            if eq_item.amount == 1:
                eq_item.delete()
            else:
                eq_item.weight -= eq_item.weight/eq_item.amount
                eq_item.amount -= 1
                eq_item.save()

            if waterMsg != "":
                messages.error(request, waterMsg)
            if foodMsg != "":
                messages.error(request, foodMsg)

            return redirect(f'/dunnorpg/items/ch{char_id}')
        except Exception as e:
            messages.error(request, f"Błąd: {e}")
            print(traceback.format_exc())
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
    try:
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

            class_skills = models.Skills_Decs.objects.filter(
                restrictions__icontains=chosen_class.name
            ).order_by('name')

            context['class'] = chosen_class
            context['theme_list'] = chosen_class.positives.split(';')
            context['class_skills'] = class_skills

            return context
    except:
        print(traceback.format_exc())

class RacesView(ListView):
    model = models.Races
    template_name = 'races.html'
    context_object_name = 'races'

    def get_queryset(self):
        races = super().get_queryset().order_by('name')
        if not self.request.user.is_superuser:
            races = races.exclude(name__startswith='|', name__endswith='|')
        return races

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

        chosen_race.Skills = [skill for skill in chosen_race.Skills.split(";") if skill]
        for skill in chosen_race.Skills:
            try:
                index = chosen_race.Skills.index(skill)
                if "-" not in skill and skill[0].isdigit():
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

        stat_names = ["INT", "SIŁ", "ZRE", "CHAR", "CEL", "SPO"]
        stat_plus = chosen_race.statPlus.split(";")
        stat_minus = chosen_race.statMinus.split(";")
        chosen_race.stats = []
        for index, stat_name in enumerate(stat_names):
            plus = int(stat_plus[index]) if index < len(stat_plus) and stat_plus[index] else 0
            minus = int(stat_minus[index]) if index < len(stat_minus) and stat_minus[index] else 0
            value = plus - minus
            if value > 0:
                display = f"+{value}"
                css_class = "text-success"
            elif value < 0:
                display = str(value)
                css_class = "text-danger"
            else:
                display = "0"
                css_class = "text-secondary"
            chosen_race.stats.append({
                "name": stat_name,
                "value": display,
                "css_class": css_class,
            })

        chosen_race.weaponsPreffered = [weapon for weapon in (chosen_race.weaponsPreffered or "").split(";") if weapon]

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
                    title = kwargs['title'],
                    amount = kwargs['amount']            
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

                                    max_weight = get_character_max_weight(char)
                                    current_weight = get_character_current_weight(char)

                                    if current_weight+itemDesc.weight <= max_weight:
                                        models.Eq.objects.create(
                                            owner = char.owner,
                                            character = char.name,
                                            name = itemDesc.name,
                                            type = itemDesc.type,
                                            weight = itemDesc.weight,
                                            durability = dur,
                                            amount = rq_object.amount
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
                                
                                max_weight = get_character_max_weight(char)
                                current_weight = get_character_current_weight(char)

                                if current_weight+itemDesc.weight <= max_weight:
                                    models.Eq.objects.create(
                                        owner = char.owner,
                                        character = char.name,
                                        name = itemDesc.name,
                                        type = itemDesc.type,
                                        weight = itemDesc.weight,
                                        durability = dur,
                                        amount = rq.amount
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
                time = data['time']
            )
            messages.warning(request, f'Added {effect.name} to {char.name}.')
        return redirect('gm_panel')

def add_mutation(request):
    if not request.user.is_superuser:
        return redirect('gm_panel')

    if request.method == 'POST':
        character = get_object_or_404(models.Character, id=request.POST.get('character'), type__iexact='Player')
        mutation = get_object_or_404(models.Mutations, id=request.POST.get('mutation'))
        current_mutations = [
            mutation_name.strip()
            for mutation_name in (character.mutation or "").split(";")
            if mutation_name.strip() and mutation_name.strip() != "-"
        ]

        if mutation.name in current_mutations:
            messages.warning(request, f"{character.name} already has mutation {mutation.name}.")
        else:
            current_mutations.append(mutation.name)
            character.mutation = ";".join(current_mutations)
            character.save()
            messages.success(request, f"Added mutation {mutation.name} to {character.name}.")

    return redirect('gm_panel')

class GMPanel(FormView):
    model = models.Requests
    template_name = 'gm_panel.html'
    form_class = AddEqItemForm
    success_url = reverse_lazy('gm_panel')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['requests'] = models.Requests.objects.all()
        context['player_characters'] = models.Character.objects.filter(hidden=False, type__iexact='Player').order_by('name')
        context['mutations'] = models.Mutations.objects.order_by('name')
        #context['effect_form'] = AddEffectForm

        return context
    
    def form_valid(self, form):
        override = form.cleaned_data.get('override')
        equip_item = form.cleaned_data.get('equip_item')
        form_data = form.save(commit=False)
        
        character = models.Character.objects.get(pk=form_data.character)
        form_data.owner = character.owner
        form_data.character = character.name
        
        item = models.Items.objects.get(pk=form_data.name)
        form_data.name = item.name
        form_data.type = item.type
        item_weight = item.weight * form_data.amount
        form_data.weight = item_weight
        
        if not override:
            max_weight = get_character_max_weight(character)
            current_weight = get_character_current_weight(character)

            if current_weight + item_weight > max_weight:
                messages.error(self.request, 'Not enough space.')
                return redirect('gm_panel')

        equipped = False
        if equip_item:
            target_hand = ""
            target_position = ""
            item_category = (item.category or "").lower()
            if form_data.amount == 1 and item_category in ["armor", "cloth", "armor_elegant"]:
                target_position = item.type
                equipped = not models.CharItems.objects.filter(
                    character=character.name,
                    position=target_position
                ).exists()
            elif form_data.amount == 1 and item_category == "weapon":
                if not models.CharItems.objects.filter(character=character.name, hand="Left").exists():
                    target_hand = "Left"
                    equipped = True
                elif not models.CharItems.objects.filter(character=character.name, hand="Right").exists():
                    target_hand = "Right"
                    equipped = True

            if equipped:
                models.CharItems.objects.create(
                    owner=character.owner,
                    character=character.name,
                    category=item.category,
                    on_use=item.on_use,
                    use_cost=item.use_cost,
                    effectsafterpen=item.effectsAfterPen,
                    effectsall=item.effectsAlways,
                    name=item.name,
                    durability=form_data.durability,
                    hand=target_hand,
                    position=target_position,
                    reloaded=True,
                    additional_description=form_data.additional_description,
                )
                messages.success(self.request, f"{item.name} equipped to {character.name}.")
                return super().form_valid(form)

            messages.warning(self.request, f"Nie udało się założyć {item.name} postaci {character.name}")
        
        try:
            existing_item = get_object_or_404(
                models.Eq,
                name=item.name,
                character=character.name,
                durability=form_data.durability,
                additional_description=form_data.additional_description,
            )
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

def parse_city_item_entry(entry):
    item_data, _, amount_raw = entry.partition("|")
    item_data = item_data.strip()

    try:
        amount = int(amount_raw)
    except (TypeError, ValueError):
        amount = 1

    item_name = item_data
    durability = None
    if "-" in item_data:
        name_part, durability_part = item_data.rsplit("-", 1)
        try:
            durability = int(durability_part)
            item_name = name_part.strip()
        except ValueError:
            pass

    return item_name, durability, amount

def format_city_item_entry(item_name, durability, amount):
    return f"{item_name}-{durability}|{amount}"

def get_durability_from_percent(durability_percent, max_durability):
    if durability_percent is None:
        return max_durability
    return math.ceil(max_durability * (durability_percent / 100))

def get_city_armor_weight_order(item):
    item_armor_weight = (item.armor_weight or "").strip().lower()
    item_armor_rank = ARMOR_WEIGHT_ORDER.get(item_armor_weight)
    if item_armor_rank is not None:
        return item_armor_rank

    armor_weight_thresholds = {
        "Helmet": [1.5, 2.5],
        "Torso": [4, 7],
        "Boots": [0.5, 1.1],
        "Gloves": [1, 2],
    }
    thresholds = armor_weight_thresholds.get(item.type)
    if thresholds is None:
        return ARMOR_WEIGHT_ORDER["all"]

    item_weight = float(item.weight)
    if item_weight < thresholds[0]:
        return ARMOR_WEIGHT_ORDER["light"]
    if item_weight < thresholds[1]:
        return ARMOR_WEIGHT_ORDER["medium"]
    return ARMOR_WEIGHT_ORDER["heavy"]

class CityShopItem(str):
    def __new__(cls, name, durability_percent, sale_index):
        obj = str.__new__(cls, name)
        obj.durability_percent = durability_percent
        obj.sale_index = sale_index
        return obj

    def __hash__(self):
        return hash((str(self), self.durability_percent, self.sale_index))

    def __eq__(self, other):
        if isinstance(other, CityShopItem):
            return self.sale_index == other.sale_index
        return str.__eq__(self, other)

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
            helmets = []
            torsos = []
            gloves = []
            boots = []
            singles = {}
            twohands = {}
            
            armor=[]
            all_armor = []
            cloth = []
            armor_elegant = []
            amulets=[]
            weaponry_singlehand=[]
            weaponry_twohand=[]
            potions = []
            other = []
            animals = []
            amounts = {}
            durabilities = {}
            durability_percents = {}
            city_prices = {}
            city_armors = {}
            armor_weight_orders = {}
            city_categories = {}
            armor_shop_categories = ["armor", "cloth", "armor_elegant"]
            
            for sale_index, item in enumerate(items):
                item_name, durability, amount = parse_city_item_entry(item)

                if int(amount) == 0:
                    continue

                item = models.Items.objects.filter(name=item_name).first()

                if item != None:
                    if durability is None:
                        durability = 100

                    item_durability = get_durability_from_percent(durability, item.maxDurability)

                    if not item.found:
                        item.found = True
                        item.save()

                    shop_item = CityShopItem(item.name, durability, sale_index)

                    amounts[shop_item] = amount
                    durabilities[shop_item] = item_durability
                    durability_percent = durability / 100
                    durability_percents[shop_item] = f"{durability:.0f}%"
                    city_prices[shop_item] = f"{item.price * 2 * durability_percent:.1f}"
                    city_armors[shop_item] = math.ceil(item.armor * durability_percent) if item.armor else item.armor
                    armor_weight_orders[shop_item] = get_city_armor_weight_order(item)
                    item_category = (item.category or "").strip().lower()
                    city_categories[shop_item] = item_category
                    if item_category in armor_shop_categories:
                        all_armor.append(shop_item)
                    elif item.type == 'Amulet':
                        amulets.append(shop_item)
                    elif item.type == 'Other':
                        if item.name.split(' ')[0] in ['Eliksir','Mikstura']:
                            potions.append(shop_item)
                        else:   
                            other.append(shop_item)
                    elif item.type == 'Animal' or item.type.lower() == 'mount armor':
                        animals.append(shop_item)
                    else:
                        if item.type in armor_types:
                            if item.type=="Helmet":
                                helmets.append(shop_item)
                            elif item.type=="Torso":
                                torsos.append(shop_item)
                            elif item.type=="Gloves":
                                gloves.append(shop_item)
                            elif item.type=="Boots":
                                boots.append(shop_item)
                        else:
                            if item.dualHanded:
                                if item.type in twohands.keys():
                                    twohands[item.type].append(shop_item)
                                else:
                                    twohands[item.type] = [shop_item]
                            else:
                                if item.type in singles.keys():
                                    singles[item.type].append(shop_item)
                                else:
                                    singles[item.type] = [shop_item]          
            

            for tw_items in twohands.values():
                weaponry_twohand += tw_items
            #weaponry_twohand.append(item.name)

            for sn_items in singles.values():
                weaponry_singlehand += sn_items
            #weaponry_singlehand.append(item.name)

            all_armor += helmets+torsos+gloves+boots
            all_armor.sort(key=lambda item_name: (armor_weight_orders.get(item_name, ARMOR_WEIGHT_ORDER["all"]), item_name))
            armor = [item_name for item_name in all_armor if city_categories.get(item_name) == "armor"]
            cloth = [item_name for item_name in all_armor if city_categories.get(item_name) == "cloth"]
            armor_elegant = [item_name for item_name in all_armor if city_categories.get(item_name) == "armor_elegant"]

            x5packets = []
            x10packets = ["Strzała","Pocisk do broni prochowej"]

            context['weaponry_singlehand'] = weaponry_singlehand
            context['weaponry_twohand'] = weaponry_twohand
            context['armor'] = armor
            context['cloth'] = cloth
            context['armor_elegant'] = armor_elegant
            context['amulets'] = amulets
            context['potions'] = potions
            context['animals'] = animals
            context['other'] = other
            context['city'] = city
            context['x5packets'] = x5packets
            context['x10packets'] = x10packets
            context['amounts'] = amounts
            context['durabilities'] = durabilities
            context['durability_percents'] = durability_percents
            context['city_prices'] = city_prices
            context['city_armors'] = city_armors
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
        item_amount = int(kwargs['amount'])
        item_durability = item.maxDurability
        item_durability_percent = 100
        requested_durability = request.GET.get("durability")
        try:
            requested_durability = int(requested_durability) if requested_durability is not None else None
        except ValueError:
            requested_durability = None
        available_amount = 0

        for ct_item in city.items.split(";"):
            ct_item_name, ct_item_durability, amount = parse_city_item_entry(ct_item)
            ct_item_durability_percent = 100 if ct_item_durability is None else ct_item_durability
            if ct_item_name == item.name and (requested_durability is None or requested_durability == ct_item_durability_percent):
                item_durability_percent = ct_item_durability_percent
                item_durability = get_durability_from_percent(item_durability_percent, item.maxDurability)
                available_amount = amount
                break

        if available_amount <= 0:
            messages.error(request, f'Za pĂłĹşno, wszystkie juĹĽ wyszĹ‚y!')
            return redirect('/dunnorpg/city')

        if item_amount > available_amount:
            item_amount = available_amount

        max_weight = get_character_max_weight(character)
        current_weight = get_character_current_weight(character)

        if current_weight+item.weight*item_amount <= max_weight:
            durability_percent = item_durability_percent / 100
            price = item.price*2*durability_percent*int(item_amount)
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

            raw_char_bonus = price * (charisma * 2) / 100
            char_bonus = float("{:.1f}".format(raw_char_bonus)) # e.g. 10.1
            price -= char_bonus

            if character.coins >= price:

                city_items = city.items.split(";")
                for ct_item in city_items:
                    ct_item_name, ct_item_durability, amount = parse_city_item_entry(ct_item)
                    ct_item_durability_percent = 100 if ct_item_durability is None else ct_item_durability
                    if ct_item_name == item.name and (requested_durability is None or requested_durability == ct_item_durability_percent):
                        index = city_items.index(ct_item)
                        if ct_item_durability is None:
                            ct_item_durability = 100

                        if int(amount)<=0:
                            messages.error(request, f'Za późno, wszystkie już wyszły!')
                            return redirect('/dunnorpg/city')

                        new_amount = int(amount)-int(item_amount)
                        if new_amount<0:
                            item_amount+=new_amount
                            new_amount = int(amount)-int(item_amount) #should be 0
                        ct_new_item = format_city_item_entry(ct_item_name, ct_item_durability, new_amount)
                        city_items[index] = ct_new_item
                        item_durability_percent = ct_item_durability
                        item_durability = get_durability_from_percent(item_durability_percent, item.maxDurability)

                city.items = ';'.join(city_items)
                city.save()

                character.coins -= price
                character.save()
                
                #if item.name in ["Strzała","Pocisk do broni prochowej"]:
                #    item_amount = item_amount*10
                try:
                    existing_item = get_object_or_404(models.Eq, name=item.name, character=character.name, durability=item_durability)
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
                        durability = item_durability,
                        amount = item_amount
                    )

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
