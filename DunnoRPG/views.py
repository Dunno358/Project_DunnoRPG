from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.apps import apps
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
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
import random
import re
from urllib.parse import urlencode
from pathlib import Path

from DunnoRPG.serializers import (CharacterSerializer, ItemSerializer,
                                  SkillsDecsSerializer, SkillsSerializer)

from . import models
from .city_discounts import CITY_SHOPS, parse_city_discounts
from .forms import CharacterSkillsForm, AddEqItemForm #, AddEffectForm
from .services.item_effects import apply_item_use_effects, fill_water
from .services.attack_criticals import resolve_critical
from .services.armor import armor_by_durability
from .services.character_effects import (
    READ_BOOKS_EFFECT, active_effects, add_active_effect, adrenaline_percent, disadvantage_count,
    effect_stat_modifier, round_effects,
)

BOOK_TYPE = 'książka'
ADVANCED_BOOK_CATEGORY = 'zaawansowana księga'
GRIMOIRE_CATEGORY = 'grymuar'
BOOK_TRADE_LOCKED = 'Sprzedaż i transfer tej książki są zablokowane do zmiany rozdziału [Czytanie].'
SKILL_REQUIREMENT = re.compile(r'(SIŁ|ZRE|INT|CHAR|CEL|SPO)\s*:?\s*(-?\d+)', re.IGNORECASE)


def current_reading_book(inventory):
    return inventory.filter(book_trade_locked=True, amount__gt=0).order_by('pk').values_list('name', flat=True).first()


def skills_available_in_editor(class_name):
    restrictions = Q(restrictions__icontains='all') | Q(restrictions__icontains='Uniwersalne')
    if class_name:
        restrictions |= Q(restrictions__icontains=class_name)
    return models.Skills_Decs.objects.filter(restrictions)


def magical_classes(class_names):
    return models.Classes.objects.filter(name__in=class_names, category__iexact='Magiczne')


def skill_requirement_error(character, details, level):
    for requirement in (getattr(details, f'reqs{level}', None) or '').split(';'):
        requirement = requirement.strip()
        if not requirement:
            continue
        match = SKILL_REQUIREMENT.fullmatch(requirement)
        if not match:
            return f'Nieprawidłowe wymaganie dla {details.name}, poz. {level}: {requirement}.'
        stat, minimum = match[1].upper(), int(match[2])
        if getattr(character, stat) < minimum:
            return f'{details.name}, poz. {level}: wymagana wartość {stat} to {minimum}.'
    return None

raceSizes = {
    "S": 0.5,
    "M": 1,
    "L": 2
}

CHAPTER_CHOICES = [
    "Tzeentch",
    "Bretonnia",
    "Averland",
    "Krasnoludy",
    "Wschodnie Ziemie",
    "Cathay",
    "Nordland",
    "Kislev",
]

CHAPTER_404_BACKGROUND_CLASSES = {
    "Tzeentch": "body-bg404-tzeentch",
    "Bretonnia": "body-bg404-bretonnia",
    "Averland": "body-bg404-nordland",
    "Krasnoludy": "body-bg404-krasnoludy",
    "Wschodnie Ziemie": "body-bg404-wschodnie-ziemie",
    "Wschód": "body-bg404-wschodnie-ziemie",
    "Cathay": "body-bg404-cathay",
    "Nordland": "body-bg404-nordland",
    "Kislev": "body-bg404-kislev",
}

CHAPTER_404_TEXT_STROKE_CLASSES = {
    "Tzeentch": "text-404-stroke-tzeentch",
    "Bretonnia": "text-404-stroke-bretonnia",
    "Averland": "text-404-stroke-nordland",
    "Krasnoludy": "text-404-stroke-krasnoludy",
    "Wschodnie Ziemie": "text-404-stroke-wschodnie-ziemie",
    "Wschód": "text-404-stroke-wschodnie-ziemie",
    "Cathay": "text-404-stroke-cathay",
    "Nordland": "text-404-stroke-nordland",
    "Kislev": "text-404-stroke-kislev",
}

CHAPTER_NAME_ALIASES = {
    "Wschód": "Wschodnie Ziemie",
}

TEXTS_404_PATH = Path(__file__).resolve().parent / "static" / "DunnoRPG" / "img" / "404" / "404_texts.json"
DEFAULT_404_TEXT = "It seems that page you're looking for doesn't exist or has been slained for Sigmar!"

def get_game_settings():
    settings, _ = models.GameSettings.objects.get_or_create(
        id=1,
        defaults={"current_chapter": CHAPTER_CHOICES[0]},
    )
    return settings

def get_current_chapter():
    return get_game_settings().current_chapter

def get_404_background_class():
    return CHAPTER_404_BACKGROUND_CLASSES.get(
        get_current_chapter(),
        CHAPTER_404_BACKGROUND_CLASSES[CHAPTER_CHOICES[0]],
    )

def get_404_text_stroke_class():
    return CHAPTER_404_TEXT_STROKE_CLASSES.get(
        get_current_chapter(),
        CHAPTER_404_TEXT_STROKE_CLASSES[CHAPTER_CHOICES[0]],
    )

def get_404_text():
    current_chapter = get_current_chapter()
    text_chapter = CHAPTER_NAME_ALIASES.get(current_chapter, current_chapter)

    try:
        texts = json.loads(TEXTS_404_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_404_TEXT

    chapter_texts = [
        text["tekst"]
        for text in texts
        if text.get("chapter") == text_chapter and text.get("tekst")
    ]
    if not chapter_texts:
        return DEFAULT_404_TEXT

    return random.choice(chapter_texts)

def render_404(request):
    return render(
        request,
        '404.html',
        {
            'background_404_class': get_404_background_class(),
            'text_404_stroke_class': get_404_text_stroke_class(),
            'current_chapter': get_current_chapter(),
            'text_404': get_404_text(),
        },
        status=404,
    )

def is_visible_for_current_chapter(value, current_chapter):
    value = (value or "").strip()
    if not value:
        return False
    if "-" not in value:
        return True
    chapter_name = value.split("-", 1)[0].strip()
    return chapter_name == current_chapter

def is_partial_request(request):
    return (
        request.GET.get("partial") == "1"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

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
    match = re.fullmatch(r"(.+?)[_-]\s*(\d+)", skill)
    if match:
        skill_name, lvl = match.groups()
    elif skill[0].isdigit():
        lvl, skill_name = skill[0], skill[1:]
    elif skill[-1].isdigit():
        skill_name, lvl = skill[:-1], skill[-1]
    else:
        return None
    skill_name = skill_name.strip()
    if not skill_name or int(lvl) < 1:
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


def parse_item_granted_skills(granted_skills):
    if not granted_skills:
        return []

    parsed_skills = []
    for raw_skill in granted_skills.split(";"):
        skill = raw_skill.strip()
        if not skill:
            continue

        parsed_skill = parse_free_skill(skill)
        if parsed_skill is None and "-" in skill:
            skill_name, skill_lvl = skill.rsplit("-", 1)
            if skill_lvl.strip().isdigit():
                parsed_skill = (skill_name.strip(), int(skill_lvl.strip()))

        if parsed_skill is not None:
            parsed_skills.append(parsed_skill)

    return parsed_skills


def book_skill_targets(granted_skills):
    targets = {}
    for name, level in granted_skills:
        key = name.casefold()
        if key not in targets or level > targets[key][1]:
            targets[key] = (name, level)
    return targets


def permanent_skills():
    return models.Skills.objects.exclude(Q(source='item') | Q(source__startswith='item:'))


def book_previous_level_error(name, level, current_level):
    if level <= 1 or current_level == level - 1:
        return None
    if current_level >= level:
        return f'Postać zna już umiejętność „{name}” na tym samym lub wyższym poziomie.'
    return f'Wymagany poprzedni poziom umiejętności „{name}” to {level - 1}.'


def sync_item_granted_skills(character):
    character_skills = models.Skills.objects.filter(owner=character.owner, character=character.name)
    item_skills = character_skills.filter(Q(source="item") | Q(source__startswith="item:"))
    retained_ids = []

    granted = {}
    equipped_items = models.CharItems.objects.filter(character=character.name)
    # Older equipment may store the GM who equipped it as its owner.
    # Only use the name alone when it identifies a single character.
    if models.Character.objects.filter(name=character.name).exclude(pk=character.pk).exists():
        equipped_items = equipped_items.filter(owner=character.owner)
    equipped_names = equipped_items.exclude(hand__in=BELT_ITEM_PLACES).values_list("name", flat=True)
    item_descs = models.Items.objects.filter(name__in=equipped_names).exclude(
        type__iexact=BOOK_TYPE,
    ).exclude(grantedSkills__isnull=True).exclude(grantedSkills="")

    for item_desc in item_descs:
        for skill_name, skill_lvl in parse_item_granted_skills(item_desc.grantedSkills):
            current = granted.get(skill_name.casefold())
            if current is None or skill_lvl > current["level"]:
                granted[skill_name.casefold()] = {
                    "name": skill_name,
                    "level": skill_lvl,
                    "source": f"item:{item_desc.name}",
                }

    # Normalize in Python: SQLite's case-insensitive lookups only handle ASCII.
    skill_descs = {}
    if granted:
        for skill_desc in models.Skills_Decs.objects.order_by("pk"):
            skill_descs.setdefault(skill_desc.name.casefold(), skill_desc)
    natural_skill_names = {
        name.casefold()
        for name in character_skills.exclude(
            Q(source="item") | Q(source__startswith="item:")
        ).values_list("skill", flat=True)
    }
    existing_item_skills = {}
    for skill in item_skills.order_by("pk"):
        existing_item_skills.setdefault(skill.skill.casefold(), skill)

    for skill_key, skill_data in granted.items():
        if skill_key in natural_skill_names:
            continue

        skill_desc = skill_descs.get(skill_key)
        if skill_desc is None:
            continue

        level_desc = getattr(skill_desc, f"level{skill_data['level']}", None)
        max_uses = getattr(skill_desc, f"useslvl{skill_data['level']}", None)
        existing = existing_item_skills.get(skill_key)
        defaults = {
            "skill": skill_desc.name,
            "category": skill_desc.category,
            "level": skill_data["level"],
            "desc": f"{skill_desc.desc} {level_desc}" if level_desc else skill_desc.desc,
            "source": skill_data["source"],
        }
        if existing is None:
            existing = models.Skills.objects.create(
                owner=character.owner, character=character.name,
                uses_left=max_uses or 0, **defaults,
            )
        else:
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save(update_fields=list(defaults))
        retained_ids.append(existing.id)

    item_skills.exclude(id__in=retained_ids).delete()


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
CHARACTER_ACCESSORY_CATEGORIES = {"accessory", "akcesoria"}
CHARACTER_ACCESSORY_TYPES = {"accessory", "akcesoria"}
CHARACTER_ACCESSORY_POSITIONS = {"accessory", "akcesoria"}
EQUIPPED_ONLY_CAPACITY_ITEM_TYPES = {"amulet", "helmet", "torso", "gloves", "boots"}
BELT_ITEM_PLACES = ("Side", "Side2")
HAND_ITEM_PLACES = {"left", "right", "side", "side2"}
MAX_BAG_ITEMS_IN_EQ = 2


def is_weapon_item(item):
    category = (item.category or "").strip().lower()
    return category == "weapon" or category.startswith("weapon_")


def attack_action_cost(item):
    light_or_medium_bow = (
        (item.type or "").strip().lower() == "bow"
        and (item.armor_weight or "").strip().lower() in {"light", "medium"}
    )
    return 1.0 if item.dualHanded and not light_or_medium_bow else 0.5


def weapon_requires_reload(item):
    return (
        (item.category or "").strip().lower() in {"weapon_range", "weapon_gun"}
        and (item.type or "").strip().lower() != "bow"
    )


MILITARY_TRAINING_SKILL = "wojskowe przeszkolenie"


def character_has_skill(character, skill_name):
    return models.Skills.objects.filter(
        character=character.name,
        skill__iexact=skill_name,
    ).exists()


def item_effective_range(item):
    if item.range != 0:
        return item.range

    item_type = (item.type or "").lower()
    ranges = {
        "pistol": 9,
        "kusza refleksyjna": 15,
        "crossbow": 16,
        "heavy crossbow": 17,
        "arbalest": 18,
        "bow": 14,
        "longbow": 16,
        "shortbow": 12,
        "musket": 18,
        "lute": 1,
        "shield": 1,
        "strzelba": 8,
        "krĂłtka strzelba": 5,
        "wand": 12,
        'flamethrower': 5,
    }
    if item_type in ranges:
        return ranges[item_type]

    bonus = 1 if item_type in ["halberd", "spear", "glaive", "trident", "broĹ„ drzewcowa"] else 0
    return 2 + bonus if item.dualHanded else 1 + bonus


def is_shield_item(item):
    return (item.type or "").lower() == "shield"


def is_military_training_polearm(item):
    return (
        item.dualHanded
        and (item.category or "").lower() == "weapon_melee"
        and item_effective_range(item) == 3
    )


def can_pair_hand_items(character, left_item, right_item):
    if not left_item or not right_item:
        return True
    if not left_item.dualHanded and not right_item.dualHanded:
        return True

    has_military_training = character_has_skill(character, MILITARY_TRAINING_SKILL)
    military_training_pair = (
        has_military_training
        and (
            (is_military_training_polearm(left_item) and is_shield_item(right_item))
            or (is_shield_item(left_item) and is_military_training_polearm(right_item))
        )
    )
    return military_training_pair


def can_equip_hand_item(character, item, hand):
    hand = hand.capitalize()
    if hand in BELT_ITEM_PLACES:
        opposite_hand = "Side2" if hand == "Side" else "Side"
        opposite = models.CharItems.objects.filter(character=character.name, hand=opposite_hand).first()
        opposite_item = models.Items.objects.filter(name=opposite.name).first() if opposite else None
        if opposite and (item.dualHanded or (opposite_item and opposite_item.dualHanded)):
            return False, "Broń dwuręczna wymaga obu wolnych miejsc przy pasie."
        return True, ""
    if hand not in {"Left", "Right"}:
        return True, ""

    opposite_hand = "Left" if hand == "Right" else "Right"
    opposite = models.CharItems.objects.filter(character=character.name, hand=opposite_hand).first()
    opposite_item = models.Items.objects.filter(name=opposite.name).first() if opposite else None

    if (
        hand == "Right"
        and item.dualHanded
        and not (
            opposite_item
            and is_shield_item(opposite_item)
            and character_has_skill(character, MILITARY_TRAINING_SKILL)
            and is_military_training_polearm(item)
        )
    ):
        return False, 'Dual-Handed weapons can only be added to left hand!'

    left_item = item if hand == "Left" else opposite_item
    right_item = item if hand == "Right" else opposite_item
    if not can_pair_hand_items(character, left_item, right_item):
        return False, 'W tej kombinacji moĹĽna poĹ‚Ä…czyÄ‡ tylko tarczÄ™ z dwurÄ™cznÄ… broniÄ… drzewcowÄ… o zasiÄ™gu 3 przy umiejÄ™tnoĹ›ci Wojskowe przeszkolenie.'

    return True, ""


def filter_hand_weapon_options(character, weapons, hand):
    allowed = []
    for eq_item in weapons:
        item = models.Items.objects.filter(name=eq_item.name).first()
        if not item:
            continue
        can_equip, _ = can_equip_hand_item(character, item, hand)
        if can_equip:
            allowed.append(eq_item)
    return allowed


def is_character_accessory_item(item):
    item_category = (item.category or "").strip().lower()
    item_type = (item.type or "").strip().lower()
    return item_category in CHARACTER_ACCESSORY_CATEGORIES or item_type in CHARACTER_ACCESSORY_TYPES


def character_accessory_items_q():
    query = Q()
    for category in CHARACTER_ACCESSORY_CATEGORIES:
        query |= Q(category__iexact=category)
    for item_type in CHARACTER_ACCESSORY_TYPES:
        query |= Q(type__iexact=item_type)
    return query


def is_character_accessory_position(position):
    return (position or "").strip().lower() in CHARACTER_ACCESSORY_POSITIONS


def get_equipped_item_for_place(character_name, place):
    if (place or "").lower() in HAND_ITEM_PLACES:
        return models.CharItems.objects.filter(character=character_name, hand=place.capitalize()).first()
    if is_character_accessory_position(place):
        return (
            models.CharItems.objects.filter(character=character_name, position__iexact="Accessory").first()
            or models.CharItems.objects.filter(character=character_name, position__iexact="Akcesoria").first()
        )
    return models.CharItems.objects.filter(character=character_name, position=place.capitalize()).first()


def get_bag_items_count_in_eq(character):
    bag_names = models.Items.objects.filter(category__iexact="bag").values_list("name", flat=True)
    return sum(
        item.amount
        for item in models.Eq.objects.filter(character=character.name, name__in=bag_names)
    )


def can_add_item_to_eq_by_limits(character, item, amount):
    if (item.category or "").strip().lower() != "bag":
        return True
    return get_bag_items_count_in_eq(character) + amount <= MAX_BAG_ITEMS_IN_EQ


def get_character_max_weight(character):
    has_mount = models.CharItems.objects.filter(character=character.name, position="Mount").exists()
    item_capacity = 0
    for item in models.Eq.objects.filter(character=character.name):
        item_desc = models.Items.objects.filter(name=item.name).first()
        if item_desc:
            if (item_desc.type or "").lower() in EQUIPPED_ONLY_CAPACITY_ITEM_TYPES:
                continue
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


def clamp_item_durability(item_desc, durability):
    try:
        durability = int(durability)
    except (TypeError, ValueError):
        durability = item_desc.maxDurability

    max_durability = item_desc.maxDurability or 0
    if max_durability > 0 and durability > max_durability:
        return max_durability
    return durability


def move_char_item_to_eq(char_item):
    character = models.Character.objects.filter(owner=char_item.owner, name=char_item.character).first()
    item_desc = get_object_or_404(models.Items, name=char_item.name)
    durability = clamp_item_durability(item_desc, char_item.durability)
    eq_item = models.Eq.objects.filter(
        character=char_item.character,
        name=char_item.name,
        durability=durability,
        additional_description=char_item.additional_description,
        use_amount=char_item.use_amount,
        reloaded=char_item.reloaded,
        book_trade_locked=False,
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
            durability=durability,
            additional_description=char_item.additional_description,
            use_amount=char_item.use_amount,
            reloaded=char_item.reloaded,
        )

    if item_desc.skillEffects != None:
        for effect in item_desc.skillEffects.split(';'):
            effect = effect.split("-")
            active_effect = models.Effects.objects.filter(character=char_item.character, name=effect[0]).first()
            if active_effect:
                active_effect.delete()

    char_item.delete()
    if character:
        sync_item_granted_skills(character)


def delete_char_item(char_item):
    character = models.Character.objects.filter(owner=char_item.owner, name=char_item.character).first()
    item_desc = get_object_or_404(models.Items, name=char_item.name)
    if char_item.position == "Mount":
        for attachment in models.CharItems.objects.filter(character=char_item.character, position__in=MOUNT_ATTACHMENT_POSITIONS):
            delete_char_item(attachment)

    if item_desc.skillEffects != None:
        for effect in item_desc.skillEffects.split(';'):
            effect = effect.split("-")
            active_effect = models.Effects.objects.filter(character=char_item.character, name=effect[0]).first()
            if active_effect:
                active_effect.delete()

    char_item.delete()
    if character:
        sync_item_granted_skills(character)


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
        owner=character.owner,
        character=character.name,
        skill__iexact='Mocna głowa',
    ).first()

    if strong_head_skill is None:
        return 3

    return 3 + strong_head_skill.level

ALCOHOL_LITE_DESC = "Odczuwasz upojenie alkoholem"
ALCOHOL_DRUNK_DESC = "Jesteś pijany"
ALCOHOL_HANGOVER_DESC = "Masz kaca"


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
        name="Kac",
    ).exists():
        return "Kac"
    return "Trzeźwy"


def is_player_animal(character):
    return (character.type or "").lower() == "gracz: zwierze"


def refresh_alcohol_effects(character, durations, description):
    for name, time in durations.items():
        effects = models.Effects.objects.filter(
            owner=character.owner, character=character.name, name=name, desc=description,
        )
        if not effects.update(time=time):
            models.Effects.objects.create(
                owner=character.owner, character=character.name, name=name, desc=description, time=time,
            )


def sync_alcohol_effects(character, previous_alcohol_level=None):
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
    character_effects = models.Effects.objects.filter(owner=character.owner, character=character.name)
    alcohol_lite_effects = character_effects.filter(name="Podpity", desc=ALCOHOL_LITE_DESC)
    alcohol_drunk_effects = character_effects.filter(
        name__in=("Pijany", "Utrudnienie"), desc=ALCOHOL_DRUNK_DESC,
    )
    hangover_effects = character_effects.filter(name__in=("Kac", "Utrudnienie"), desc=ALCOHOL_HANGOVER_DESC)

    if alcohol_level <= 0:
        alcohol_lite_effects.delete()
        alcohol_drunk_effects.delete()
        if previous_alcohol_level > drunkenness_limit:
            refresh_alcohol_effects(character, {"Kac": 1000, "Utrudnienie": 1}, ALCOHOL_HANGOVER_DESC)
    elif alcohol_level > drunkenness_limit:
        alcohol_lite_effects.delete()
        hangover_effects.delete()
        refresh_alcohol_effects(character, {"Pijany": 1000, "Utrudnienie": 1000}, ALCOHOL_DRUNK_DESC)
    else:
        alcohol_drunk_effects.delete()
        hangover_effects.delete()
        refresh_alcohol_effects(character, {"Podpity": 1000}, ALCOHOL_LITE_DESC)


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
        current_chapter = get_current_chapter()
        allowed_types = [
            character_type
            for character_type in qs.exclude(type__isnull=True).values_list('type', flat=True).distinct()
            if is_visible_for_current_chapter(character_type, current_chapter)
        ]
        qs = qs.filter(type__in=allowed_types)

        selected_type = self.request.GET.get('character_type', 'Player')
        if selected_type:
            qs = qs.filter(type=selected_type)

        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        base_qs = self.get_base_queryset()
        base_qs = base_qs.exclude(type__isnull=True)
        selected_type = self.request.GET.get('character_type', 'Player')
        current_chapter = get_current_chapter()
        character_types = [
            character_type
            for character_type in base_qs.values_list('type', flat=True).distinct()
            if is_visible_for_current_chapter(character_type, current_chapter)
        ]

        context['selected_type'] = selected_type
        context['character_types'] = sorted(character_types)
        context['current_chapter'] = current_chapter
        context['characters_count'] = self.get_queryset().count()
        context['copy_default_names'] = {
            character.id: get_next_character_copy_name(character.name)
            for character in context['characters']
        }

        return context
    
class AddCharacterView(APIView):
    template_name = 'character_add.html'
    renderer_classes = [TemplateHTMLRenderer]

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

class ArchiveCharacter(APIView):
    def post(self, request, char_id):
        character = get_object_or_404(models.Character, id=char_id, hidden=False)
        if not request.user.is_superuser and character.owner != request.user.username:
            raise Http404('Invalid character')

        character.hidden = True
        character.save(update_fields=['hidden'])
        return JsonResponse({
            'id': character.id,
            'name': character.name,
            'message': f"Zarchiwizowano {character.name}",
        })

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
    renderer_classes = [TemplateHTMLRenderer]

    def get(self, request, *args, **kwargs):
        user = self.request.user
        id = kwargs['id']
        chosen_character = get_object_or_404(models.Character, id=id)
        available_skills = list(skills_available_in_editor(chosen_character.chosen_class).order_by('name').values())
        available_ids = {skill['id'] for skill in available_skills}

        character_skills_queryset = models.Skills.objects.filter(
            owner=chosen_character.owner,
            character=chosen_character.name
        ).order_by('skill')
        skill_names = [skill.skill for skill in character_skills_queryset]
        skill_details_ids = {
            skill['name']: skill['id']
            for skill in models.Skills_Decs.objects.filter(name__in=skill_names).values('id', 'name')
        }
        for skill in character_skills_queryset:
            skill.original_id = skill_details_ids.get(skill.skill)
            skill.book_upgrade_locked = skill.book_level is not None and skill.original_id not in available_ids
        
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
            "exp_animal_characters": models.Character.objects.filter(
                owner=chosen_character.owner,
                type__iexact="Gracz: Zwierze",
                hidden=False,
            ).exclude(id=chosen_character.id).order_by("name"),
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

@method_decorator(never_cache, name='dispatch')
class CharacterDetails(DetailView):
    model = models.Character
    template_name = 'character_detail.html'

    def get_template_names(self):
        if self.request.headers.get("X-Character-Fragment") == "1":
            return ['dunnorpg/character_details_data.html']
        return super().get_template_names()

    def get_object(self,queryset=None):
        char_id = self.kwargs.get('id')
        character = get_object_or_404(models.Character, id=char_id)
        if character.owner != self.request.user.username and self.request.user.is_superuser == False:
            raise Http404('Invalid character')
        return character

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        chosen = self.get_object()
        sync_item_granted_skills(chosen)
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
        ammo_descriptions = {item.name: item for item in models.Items.objects.filter(name__in=eq_items.values_list('name', flat=True))}
        for item in eq_items:
            description = ammo_descriptions.get(item.name)
            is_ammo = description and (description.category == 'ammo' or (description.type or '').lower() == 'amunicja')
            if is_ammo or any(word in item.name.lower() for word in ('pocisk', 'strzała', 'bełt')):
                item.attack_dmg_modifier = description.dmgModifier if description else 1
                item.attack_ap = description.AP if description else 0
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
        accessory_names = models.Items.objects.filter(character_accessory_items_q()).values_list('name', flat=True)
        eq_amulets_qs = models.Eq.objects.filter(character=chosen.name, type='Amulet').exclude(name__in=accessory_names).order_by('name')
        eq_accessories_qs = models.Eq.objects.filter(character=chosen.name, name__in=accessory_names).order_by('name')
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
        weapon_names = models.Items.objects.filter(category__startswith="weapon_").values_list("name", flat=True)
        eq_weapons_qs = models.Eq.objects.filter(character=chosen.name, name__in=weapon_names).order_by('name')
        
        context['helmet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Helmet').first()
        context['torso'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Torso').first()
        context['gloves'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Gloves').first()
        context['boots'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Boots').first()
        context['amulet'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Amulet').first()
        context['accessory'] = get_equipped_item_for_place(serializer.data['name'], 'Accessory')
        context['mount'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount').first()
        context['mount_mobility'] = (
            models.Items.objects.filter(name=context['mount'].name).values_list('mobility', flat=True).first()
            if context['mount'] else None
        )
        context['mount_armor'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_armor').first()
        context['mount_horseshoes'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_horseshoes').first()
        context['mount_saddle'] = models.CharItems.objects.filter(character=serializer.data['name'], position='Mount_saddle').first()
        context['leftItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Left').first()
        context['rightItem'] = models.CharItems.objects.filter(character=serializer.data['name'], hand='Right').first()
        for hand in ('left', 'right'):
            equipped_item = context[f'{hand}Item']
            context[f'{hand}Weapon'] = models.Items.objects.filter(name=equipped_item.name).first() if equipped_item else None
            description = context[f'{hand}Weapon']
            if equipped_item and description:
                equipped_item.attack_cost = attack_action_cost(description)
                equipped_item.needs_reload = weapon_requires_reload(description) and not equipped_item.reloaded
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
        context['effect_definitions'] = models.Effects_Decs.objects.order_by('name')
        context['alcohol_state'] = get_alcohol_state(chosen, alcohol_level, drunkenness_limit)
        context['is_over_drunkenness_limit'] = alcohol_level > drunkenness_limit
        context['exp_animal_characters'] = models.Character.objects.filter(
            owner=chosen.owner,
            type__iexact="Gracz: Zwierze",
            hidden=False,
        ).exclude(id=chosen.id).order_by('name')
        
        context['belt_slots'] = []
        for number, place in enumerate(BELT_ITEM_PLACES, 1):
            equipped = get_equipped_item_for_place(chosen.name, place)
            opposite_place = "Side2" if place == "Side" else "Side"
            opposite = get_equipped_item_for_place(chosen.name, opposite_place)
            opposite_desc = models.Items.objects.filter(name=opposite.name).first() if opposite else None
            context['belt_slots'].append({
                'number': number,
                'place': place,
                'item': equipped,
                'blocked': bool(opposite_desc and opposite_desc.dualHanded),
                'weapons': filter_hand_weapon_options(chosen, eq_weapons_qs, place),
            })
        context['eq_weapons'] = eq_weapons_qs
        context['eq_left_hand_weapons'] = filter_hand_weapon_options(chosen, eq_weapons_qs, "Left")
        context['eq_right_hand_weapons'] = filter_hand_weapon_options(chosen, eq_weapons_qs, "Right")
        context['eq_helmets'] = eq_helmets_qs
        context['eq_torsos'] = eq_torsos_qs
        context['eq_gloves'] = eq_gloves_qs
        context['eq_boots'] = eq_boots_qs
        context['eq_amulets'] = eq_amulets_qs
        context['eq_accessories'] = eq_accessories_qs
        context['eq_mounts'] = eq_mounts_qs
        context['eq_mounts_armor'] = eq_mounts_armor_qs
        context['eq_mounts_horseshoes'] = eq_mounts_horseshoes_qs
        context['eq_mounts_saddles'] = eq_mounts_saddles_qs

        return context 
    
def valid_disadvantage_rolls(request, character):
    rolls = request.POST.getlist('effect_disadvantage')
    return len(rolls) == disadvantage_count(character) and all(roll in ('1', '2', '3', '4', '5', '6') for roll in rolls)


@require_POST
def confirm_parry(request, char_id):
    with transaction.atomic():
        char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
            return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
        if not valid_disadvantage_rolls(request, char):
            return JsonResponse({'error': 'Sprawdź rzuty K6 za utrudnienia i otwórz formularz ponownie.'}, status=409)
        try:
            weapon_id = int(request.POST.get('weapon_id', ''))
            used = int(request.POST.get('advantage_used', 0))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Nieprawidłowe dane parowania.'}, status=400)
        weapon = get_object_or_404(models.CharItems.objects.select_for_update(), id=weapon_id, character=char.name, hand__in=('Left', 'Right'))
        description = get_object_or_404(models.Items, name=weapon.name)
        if description.category == 'shield' or (description.type or '').lower() == 'shield':
            return JsonResponse({'error': 'Tarcza używa wyłącznie wartości bloku.'}, status=400)
        expected_used = max(-2, min(2, char.advantageBalance))
        if used != expected_used:
            return JsonResponse({'error': 'Bilans przewag zmienił się. Otwórz ponownie formularz parowania.'}, status=409)
        char.advantageBalance -= used
        char.save(update_fields=['advantageBalance'])
        if request.POST.get('damages_weapon') == 'true':
            weapon.durability = max(0, weapon.durability - 1)
            weapon.save(update_fields=['durability'])
        percent = round(100 * weapon.durability / description.maxDurability) if description.maxDurability > 0 else 0
        return JsonResponse({'advantageBalance': char.advantageBalance, 'durability': weapon.durability,
                             'durability_percent': percent})


@require_POST
def confirm_dodge(request, char_id):
    with transaction.atomic():
        char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
            return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
        if not valid_disadvantage_rolls(request, char):
            return JsonResponse({'error': 'Sprawdź rzuty K6 za utrudnienia i otwórz formularz ponownie.'}, status=409)
        try:
            used = int(request.POST.get('advantage_used', 0))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Nieprawidłowe dane uniku.'}, status=400)
        if used != max(-2, min(2, char.advantageBalance)):
            return JsonResponse({'error': 'Bilans przewag zmienił się. Otwórz ponownie formularz uniku.',
                                 'advantageBalance': char.advantageBalance}, status=409)
        char.advantageBalance -= used
        char.save(update_fields=['advantageBalance'])
        return JsonResponse({'advantageBalance': char.advantageBalance})


@require_POST
def confirm_attack(request, char_id):
    with transaction.atomic():
        char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
            return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
        if not valid_disadvantage_rolls(request, char):
            return JsonResponse({'error': 'Sprawdź rzuty K6 za utrudnienia i otwórz formularz ponownie.'}, status=409)
        try:
            weapon_id = int(request.POST.get('weapon_id', ''))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Nieprawidłowa broń.'}, status=400)
        weapon = get_object_or_404(models.CharItems.objects.select_for_update(), id=weapon_id, character=char.name, hand__in=('Left', 'Right'))
        description = get_object_or_404(models.Items, name=weapon.name)
        if weapon_requires_reload(description) and not weapon.reloaded:
            return JsonResponse({'error': 'Najpierw przeładuj broń.', 'reloaded': False, 'needs_reload': True,
                                 'actionLeft': char.actionLeft}, status=409)
        cost = attack_action_cost(description) if char.inFight else 0
        if char.actionLeft < cost:
            return JsonResponse({'error': f'Za mało akcji. Atak wymaga {cost:g} akcji. Pozostało {char.actionLeft:g} akcji.',
                                 'actionLeft': char.actionLeft}, status=400)
        try:
            damage_dealt = int(request.POST.get('damage_dealt', 0))
            if not 0 <= damage_dealt <= 2_147_483_647 - char.fight_damage_dealt:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Nieprawidłowa wartość zadanych obrażeń.'}, status=400)

        try:
            used = int(request.POST.get('advantage_used', 0))
            accuracy_roll = int(request.POST.get('accuracy_roll', 10))
            piercing_choice = request.POST.get('piercing_choice', 'ignore_block')
            if not 1 <= accuracy_roll <= 20 or piercing_choice not in ('ignore_block', 'ap'):
                raise ValueError('Nieprawidłowy rzut lub wybór skutku krytycznego.')
            expected_used = max(-2, min(2, char.advantageBalance))
            if used != expected_used:
                return JsonResponse({'error': 'Bilans przewag zmienił się. Otwórz ponownie formularz ataku.', 'advantageBalance': char.advantageBalance}, status=409)
            ammo = None
            ammo_id = request.POST.get('ammo_id')
            if ammo_id:
                ammo_id = int(ammo_id)
                alternate = request.POST.get('alternate_attack') == 'true' and (description.altAttack or '').strip().lower() not in ('', 'none', '-')
                if description.category not in ('weapon_range', 'weapon_gun') and not alternate:
                    raise ValueError('Ta broń nie korzysta z amunicji.')
                amount = int(request.POST.get('ammo_amount', 0))
                ammo = get_object_or_404(models.Eq.objects.select_for_update(), id=ammo_id, character=char.name)
                if amount < 1 or amount > ammo.amount:
                    raise ValueError('Nieprawidłowa ilość amunicji lub za mało amunicji.')
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Sprawdź bilans przewag i ilość dostępnej amunicji.'}, status=400)

        # The attack dialog calculates damage before the target's defenses.
        char.advantageBalance -= used
        char.actionLeft -= cost
        critical = resolve_critical(accuracy_roll, description.dmg_type, piercing_choice)
        if char.inFight and critical['kind'] != 'failure':
            char.fight_damage_dealt += damage_dealt
        if critical.get('self_damage'):
            char.HP -= critical['self_damage']
        char.save(update_fields=['advantageBalance', 'HP', 'actionLeft', 'fight_damage_dealt'])
        if critical.get('effect_name'):
            add_active_effect(char.owner, char.name, critical['effect_name'], 1, critical['effect_description'])
        durability_loss = math.ceil(max(0, description.maxDurability) * critical.get('durability_loss', 0))
        if request.POST.get('damages_weapon') == 'true':
            durability_loss += 1
        if durability_loss:
            weapon.durability = max(0, weapon.durability - durability_loss)
            weapon.save(update_fields=['durability'])
        if ammo:
            if weapon_requires_reload(description):
                weapon.reloaded = False
                weapon.save(update_fields=['reloaded'])
            ammo.amount -= amount
            if ammo.amount:
                ammo.save(update_fields=['amount'])
            else:
                ammo.delete()
        durability_percent = round(100 * weapon.durability / description.maxDurability) if description.maxDurability > 0 else 0
        return JsonResponse({'advantageBalance': char.advantageBalance, 'durability': weapon.durability,
                             'durability_percent': durability_percent, 'critical': critical, 'hp': char.HP,
                             'actionLeft': char.actionLeft, 'reloaded': weapon.reloaded,
                             'needs_reload': weapon_requires_reload(description) and not weapon.reloaded})


@require_POST
def reload_weapon(request, char_id, item_id):
    with transaction.atomic():
        char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
            return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
        weapon = get_object_or_404(
            models.CharItems.objects.select_for_update(), id=item_id,
            character=char.name, hand__in=('Left', 'Right'),
        )
        description = get_object_or_404(models.Items, name=weapon.name)
        if not weapon_requires_reload(description):
            return JsonResponse({'error': 'Ta broń nie wymaga przeładowania.'}, status=400)
        if weapon.reloaded:
            return JsonResponse({'error': 'Broń jest już przeładowana.', 'reloaded': True, 'needs_reload': False,
                                 'actionLeft': char.actionLeft}, status=409)
        if char.inFight and char.actionLeft < 0.5:
            return JsonResponse({'error': f'Za mało akcji. Przeładowanie wymaga 0,5 akcji. Pozostało {char.actionLeft:g} akcji.',
                                 'actionLeft': char.actionLeft}, status=400)
        if char.inFight:
            char.actionLeft -= 0.5
            char.save(update_fields=['actionLeft'])
        weapon.reloaded = True
        weapon.save(update_fields=['reloaded'])
        return JsonResponse({'actionLeft': char.actionLeft, 'reloaded': True, 'needs_reload': False})


class TakeItemDurFromAttack(APIView):
    def get(self, request, *args, **kwargs):
        item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
        if item.durability >=0:
            item.durability-=1
        item.save()
        return Response("OK")

class calculateGettingHit(APIView):
    def _armor_value(self, item):
        if not item:
            return 0

        item_desc = models.Items.objects.filter(name=item.name).first()
        if not item_desc or item_desc.armor == 0:
            return 0

        return armor_by_durability(item_desc.armor, item.durability)

    def _durability_percent(self, item):
        item_desc = models.Items.objects.filter(name=item.name).first()
        max_durability = getattr(item_desc, "maxDurability", 0) or 0
        if max_durability <= 0:
            return "(0%)"

        return f"({item.durability / max_durability:.0%})"

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            dmg = max(int(data.get('dmg', 0)), 0)
            ap_percent = min(max(int(data.get('ap', 0)), 0), 100)
            barrier = max(int(data.get('barrier', 0)), 0)
            ignore_armor = data.get('ignore_armor', False) in (True, 1, '1', 'true', 'True')
            parts = data.get('parts') or []
            valid_parts = {'head', 'torso', 'hands', 'legs'}
            parts = [part for part in parts if part in valid_parts]

            if not parts:
                return JsonResponse({"error": "Wybierz miejsce obrażeń."}, status=400)

            if len(parts) != 1 and (len(parts) != 4 or set(parts) != valid_parts):
                return JsonResponse({"error": "Wybierz jedną część ciała albo całe ciało."}, status=400)
            armor_override = None
            if data.get('armor') is not None:
                armor_override = float(data['armor'])
                if not math.isfinite(armor_override) or armor_override < 0:
                    return JsonResponse({"error": "Pancerz musi być nieujemną liczbą."}, status=400)
                armor_override = math.ceil(armor_override)

            with transaction.atomic():
                char = get_object_or_404(models.Character.objects.select_for_update(), id=kwargs['char_id'])
                if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
                    return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
                deferred = dmg * adrenaline_percent(char) // 100
                char.deferred_damage += deferred
                result = self.apply_damage(char, dmg - deferred, parts, barrier, ap_percent, ignore_armor, armor_override)
                if deferred:
                    result['message'] += f' Adrenalina odroczyła {deferred} obrażeń do końca rundy.'
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({"error": f"Błąd liczenia obrażeń: {e}"}, status=400)

    def apply_damage(self, char, dmg, parts, barrier, ap_percent=0, ignore_armor=False, armor_override=None):
        valid_parts = {'head', 'torso', 'hands', 'legs'}
        hp_before = char.HP

        barrier_blocked = min(dmg, barrier)
        dmg_after_barrier = dmg - barrier_blocked
        char.barrier = barrier - barrier_blocked

        ap_damage = int(dmg_after_barrier * ap_percent / 100) if dmg_after_barrier > 0 and not ignore_armor else 0
        dmg_for_armor = max(dmg_after_barrier - ap_damage, 0)

        items = {
            'head': models.CharItems.objects.filter(character=char.name, position='Helmet').first(),
            'torso': models.CharItems.objects.filter(character=char.name, position='Torso').first(),
            'legs': models.CharItems.objects.filter(character=char.name, position='Boots').first(),
            'hands': models.CharItems.objects.filter(character=char.name, position='Gloves').first(),
        }

        whole_body_armor = math.ceil(sum(self._armor_value(items[part]) for part in valid_parts) / 4) if len(parts) == 4 else None
        penetration_by_part = {}
        for part in parts:
            armor_value = 0 if ignore_armor else self._armor_value(items[part])
            if not ignore_armor and whole_body_armor is not None:
                armor_value = whole_body_armor
            if not ignore_armor and armor_override is not None:
                armor_value = armor_override
            penetration_by_part[part] = max(dmg_for_armor - armor_value, 0)

        armor_damage = max(penetration_by_part.values(), default=0)
        max_penetration_parts = [
            part for part, penetration in penetration_by_part.items()
            if penetration == armor_damage and penetration > 0
        ]
        deadly = any(part in {'head', 'torso'} for part in max_penetration_parts) or not max_penetration_parts
        hp_loss = ap_damage + armor_damage

        if hp_loss > 0:
            char.HP -= hp_loss
            if char.HP <= 0:
                char.HP = 0 if deadly else 1

        updated_armor = {}
        destroyed_count = 0
        for part in [] if ignore_armor else parts:
            item = items[part]
            if not item:
                continue

            item.durability = max(item.durability - dmg_after_barrier, 0)
            if item.durability == 0:
                destroyed_count += 1
            item.save()
            updated_armor[part] = {
                "durability": item.durability,
                "durability_percent": self._durability_percent(item),
                "armor": self._armor_value(item),
            }

        if char.inFight:
            char.fight_damage_taken += dmg
        char.save(update_fields=['HP', 'barrier', 'fight_damage_taken', 'deferred_damage'])
        actual_hp_loss = hp_before - char.HP
        deadly_wound = char.HP == 0

        if dmg > 0 and dmg_after_barrier == 0:
            message = "Bariera zablokowała obrażenia."
        elif actual_hp_loss == 0:
            message = "Obrażenia nie przebiły pancerza."
        else:
            message = f"Stracono {actual_hp_loss} PŻ z tego ataku."

        if deadly_wound:
            message += " Postać została śmiertelnie ranna."
        if destroyed_count:
            message += f" Krytycznie uszkodzono {destroyed_count} elementów pancerza."

        return {
            "message": message,
            "hp": char.HP,
            "barrier": char.barrier,
            "hp_lost": actual_hp_loss,
            "deadly_wound": deadly_wound,
            "armor": updated_armor,
        }


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
        item_desc = get_object_or_404(models.Items, name=item.name)

        if not can_add_item_to_eq_by_limits(char, item_desc, 1):
            messages.error(request, f"{char.name} moze miec maksymalnie {MAX_BAG_ITEMS_IN_EQ} torby w ekwipunku.")
            return redirect(f"/dunnorpg/character_detail/{kwargs['char_id']}")
        
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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Brak dostępnych punktów.'}, status=400)
            messages.error(request, 'Not enough points.')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'stat': stat,
                'value': getattr(character, stat),
                'points_left': character.points_left,
            })

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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Statystyka nie może być niższa niż 0.'}, status=400)
            messages.error(request, 'Stat cannot be lower than 0.')
            return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
                
        character.points_left += 1
        character.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'stat': stat,
                'value': getattr(character, stat),
                'points_left': character.points_left,
            })

        return redirect(f'/dunnorpg/character_add_skills/{char_id}/')

class Skills(APIView):
    serializer_class = SkillsDecsSerializer
    template_name = 'skills.html'
    renderer_classes = [TemplateHTMLRenderer]

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
    renderer_classes = [TemplateHTMLRenderer]

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

@transaction.atomic
def skill_add(request,char_id,skill_id,lvl):
    character = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (character.owner != request.user.username and not request.user.is_superuser):
        return HttpResponse('Brak dostępu do postaci.', status=403)
    skill_details = get_object_or_404(models.Skills_Decs, id=skill_id)
    if not skills_available_in_editor(character.chosen_class).filter(pk=skill_details.pk).exists():
        messages.error(request, f'{skill_details.name} nie jest dostępna w edycji tej postaci.')
        return redirect('character_add_skills', character.id)
    lvl = min(int(lvl), 4)

    while lvl > 0 and not getattr(skill_details, f"level{lvl}", None):
        lvl -= 1
    error = skill_requirement_error(character, skill_details, lvl) if lvl > 0 else 'Brak dostępnego poziomu umiejętności.'
    reqOK = not error
    if error:
        messages.error(request, error)


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
    

@require_POST
def enter_or_leave_fight(request, char_id):
    requested_state = request.POST.get("in_fight")
    if requested_state not in {"true", "false"}:
        return JsonResponse({"error": "Nieprawidłowy stan walki."}, status=400)
    in_fight = requested_state == "true"
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    skill_uses = {}

    with transaction.atomic():
        character = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (character.owner != request.user.username and not request.user.is_superuser):
            return JsonResponse({"error": "Brak dostępu do postaci."}, status=403)

        if character.inFight != in_fight:
            character.inFight = in_fight
            character.actionLeft = 1.0
            character.advantageBalance = 0
            character.round_mobility_bonus = 0
            fields = ["inFight", "actionLeft", "advantageBalance", "fight_summary", "round_mobility_bonus"]
            if in_fight:
                character.fight_exp_gained = 0
                character.fight_damage_taken = 0
                character.fight_damage_dealt = 0
                character.fight_start_hp = character.HP
                character.fight_summary = {}
                fields.extend(["fight_exp_gained", "fight_damage_taken", "fight_damage_dealt", "fight_start_hp"])
            else:
                summary = {
                    "exp_gained": character.fight_exp_gained,
                    "damage_taken": character.fight_damage_taken,
                    "damage_dealt": character.fight_damage_dealt,
                    "hp_difference": character.HP - character.fight_start_hp if character.fight_start_hp is not None else 0,
                }
                character.fight_summary = summary if any(summary.values()) else {}
                character.counter = 0
                character.counter2 = 0
                fields.extend(["counter", "counter2"])
                skills = list(models.Skills.objects.filter(
                    character=character.name, owner=character.owner,
                ).only("skill", "level", "uses_left"))
                skill_descriptions = {
                    description.name: description
                    for description in models.Skills_Decs.objects.filter(
                        name__in=[skill.skill for skill in skills],
                    ).only("name", "useslvl1", "useslvl2", "useslvl3", "useslvl4")
                }
                skills_to_reset = []
                for skill in skills:
                    description = skill_descriptions.get(skill.skill)
                    max_uses = getattr(description, f"useslvl{skill.level}", None)
                    if max_uses is not None:
                        skill_uses[skill.pk] = max_uses
                        if skill.uses_left != max_uses:
                            skill.uses_left = max_uses
                            skills_to_reset.append(skill)
                models.Skills.objects.bulk_update(skills_to_reset, ["uses_left"])
            character.save(update_fields=fields)
        elif is_ajax and not in_fight:
            skill_uses = dict(models.Skills.objects.filter(
                character=character.name, owner=character.owner,
            ).values_list("id", "uses_left"))

    if not is_ajax:
        return redirect("character_detail", character.id)

    chosen_class = models.Classes.objects.filter(name=character.chosen_class).first() if in_fight else None
    return JsonResponse({
        "in_fight": character.inFight,
        "action_left": character.actionLeft,
        "advantage_balance": character.advantageBalance,
        "skill_uses": skill_uses,
        "panel_html": render_to_string(
            "dunnorpg/character_combat_panel.html", {"character": character, "class": chosen_class}, request=request,
        ),
    })

@require_POST
def dismiss_fight_summary(request, char_id):
    character = get_object_or_404(models.Character, id=char_id)
    if character.owner != request.user.username and not request.user.is_superuser:
        return JsonResponse({"error": "Brak uprawnień."}, status=403)
    character.fight_summary = {}
    character.save(update_fields=["fight_summary"])
    return JsonResponse({"success": True})

@transaction.atomic
def skill_delete(request,char_id,skill_id):
    character = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (character.owner != request.user.username and not request.user.is_superuser):
        return HttpResponse('Brak dostępu do postaci.', status=403)
    skill = get_object_or_404(models.Skills, id=skill_id, owner=character.owner, character=character.name)
    if skill.book_level is not None:
        messages.error(request, f'{skill.skill} została zdobyta z książki i nie można jej usunąć.')
        return redirect('character_add_skills', character.id)
    skill_details = get_object_or_404(models.Skills_Decs, name=skill.skill)

    if skill.source == "natural_free":
        messages.error(request, f'{skill.skill} jest darmową umiejętnością z rasy lub klasy i nie można jej usunąć.')
        return redirect(f'/dunnorpg/character_add_skills/{char_id}/')
    
    character.points_left += skill.level*int(skill_details.cost)
    character.save()
    skill.delete()
    return redirect(f'/dunnorpg/character_add_skills/{char_id}/')


def skill_upgrade(request, char_id, skill_id):
    return change_skill_level(request, char_id, skill_id, step=1)


def skill_downgrade(request, char_id, skill_id):
    return change_skill_level(request, char_id, skill_id, step=-1)


@transaction.atomic
def change_skill_level(request, char_id, skill_id, step):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    character = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (character.owner != request.user.username and not request.user.is_superuser):
        if is_ajax:
            return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
        return HttpResponse('Brak dostępu do postaci.', status=403)

    skill = get_object_or_404(
        models.Skills.objects.select_for_update(), id=skill_id, owner=character.owner, character=character.name,
    )
    details = get_object_or_404(models.Skills_Decs, name=skill.skill)
    new_level = skill.level + step if skill.level is not None else None
    level_description = getattr(details, f'level{new_level}', None)
    error = None
    if step < 0 and skill.book_level is not None and skill.level <= skill.book_level:
        error = f'{skill.skill}: poziom zdobyty z książki to poziom minimalny.'
    elif step > 0 and skill.book_level is not None and not skills_available_in_editor(character.chosen_class).filter(pk=details.pk).exists():
        error = f'{skill.skill} nie jest dostępna w edycji tej postaci.'
    elif not level_description:
        error = f'{skill.skill}: Osiągnięto już maksymalny poziom!' if step > 0 else f'{skill.skill}: Niżej się nie da!'
    elif step > 0:
        error = skill_requirement_error(character, details, new_level)
        if not error and (character.points_left or 0) < int(details.cost):
            error = f'Za mało punktów, żeby ulepszyć {skill.skill}.'

    if error:
        if is_ajax:
            return JsonResponse({'error': error}, status=400)
        messages.error(request, error)
    else:
        skill.level = new_level
        skill.desc = f'{details.desc} {level_description}'
        skill.uses_left = getattr(details, f'useslvl{new_level}') or 0
        character.points_left -= step * int(details.cost)
        skill.save(update_fields=['level', 'desc', 'uses_left'])
        character.save(update_fields=['points_left'])
        if is_ajax:
            return JsonResponse({'level': skill.level, 'points_left': character.points_left})

    return redirect('character_add_skills', character.id)


def create_character(request,name,char_class,race,type,owner,exp):
    try:
        if not name.strip():
            messages.error(request, "Brak nazwy postaci")
            return redirect('character_add')

        race =  get_object_or_404(models.Races, name=race)
        maxHP = race.hp
        size_dict = {"S": 0.5, "M": 1, "L": 2}
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
            size=size_dict.get(str(race.size).upper(), race.size),
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
            if not effect:
                continue
            eff_name = effect[:-2]
            parts = effect.split("-")
            eff_nr = parts[len(parts)-1]
            #eff_desc = models.get_object_or_404(models.Effects_Decs, name=eff_name)
            add_active_effect(owner, name, eff_name, 1)

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
@transaction.atomic
def del_eq_item(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    obj_id = str(kwargs['obj_id'])
    if obj_id.startswith("char-"):
        char_item_id = obj_id.split("-", 1)[1]
        if not char_item_id.isdigit():
            messages.error(request, "Nieprawidlowy przedmiot do usuniecia.")
            return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

        char_item = get_object_or_404(models.CharItems, id=int(char_item_id), character=char.name)
        delete_char_item(char_item)
        return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

    inventory = models.Eq.objects.select_for_update().filter(character=char.name)
    if obj_id.startswith("eq-"):
        eq_item_id = obj_id.split("-", 1)[1]
        if not eq_item_id.isdigit():
            messages.error(request, "Nieprawidlowy przedmiot do usuniecia.")
            return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

        item = get_object_or_404(inventory, id=int(eq_item_id))
        item_desc = get_object_or_404(models.Items, name=item.name)
    else:
        item_desc = get_object_or_404(models.Items, id=obj_id)
        item = inventory.filter(name=item_desc.name).first()
        if item is None:
            raise Http404

    if item.book_trade_locked:
        messages.error(request, 'Czytanej książki nie można usunąć przed zmianą rozdziału.')
        return redirect('items', char_id=char.id)

    amount = kwargs['amount']
    if item.amount <= amount:
        item.delete()
    else:
        item.amount -= amount
        item.weight -= item_desc.weight * amount
        item.save(update_fields=['amount', 'weight'])
    return redirect('items', char_id=char.id)
@transaction.atomic
def sell_item(request, **kwargs):
    try:
        city = get_object_or_404(models.Cities, visiting=True)
        char = get_object_or_404(models.Character.objects.select_for_update(), id=kwargs['char_id'])
        item_ref = str(kwargs['item_id'])
        source_type = "eq"
        source_id = item_ref
        if "-" in item_ref:
            source_type, source_id = item_ref.split("-", 1)
        if not source_id.isdigit() or source_type not in {"eq", "char"}:
            messages.error(request, "Nieprawidlowy przedmiot do sprzedazy.")
            return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

        if source_type == "char":
            eqItem = get_object_or_404(models.CharItems, id=int(source_id), character=char.name)
            amount = 1
        else:
            eqItem = get_object_or_404(models.Eq.objects.select_for_update(), id=int(source_id), character=char.name)
            if eqItem.book_trade_locked:
                messages.error(request, BOOK_TRADE_LOCKED)
                return redirect('items', char_id=char.id)
            amount = int(kwargs['amount'])

        itemDesc = get_object_or_404(models.Items, name=eqItem.name)
        
        if source_type == "eq" and amount>eqItem.amount:
            messages.error(request, f"Hola, hola! Nie masz tego tyle! Masz {eqItem.amount} sztuk tego przedmiotu. ({itemDesc.name})")
            return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")

        charisma = char.CHAR + effect_stat_modifier(char, "CHAR")
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
        
        durability = clamp_item_durability(itemDesc, eqItem.durability)
        durability_percent = durability / itemDesc.maxDurability if itemDesc.maxDurability else 0

        raw_base_price = itemDesc.price*durability_percent*amount
        base_price = float("{:.1f}".format(raw_base_price)) # e.g. 10.1

        raw_char_bonus = round(((charisma*4)*base_price)/100)
        char_bonus = float("{:.1f}".format(raw_char_bonus))

        price = base_price + char_bonus #Get 100% of calculated price + [charisma*4]% bonus
        if price < 0:
            price = 0

        char.coins += price
        char.save()

        if source_type == "char":
            delete_char_item(eqItem)
        else:
            eqItem.amount -= amount
            if eqItem.amount==0:
                eqItem.delete()
            else:
                eqItem.weight -= itemDesc.weight * amount
                eqItem.save()

        messages.success(request, f"Sprzedano {amount}x {itemDesc.name} za {price} monet! Obecny majątek: {char.coins} monet.")
    except:
        messages.error(request, f"Gdzie chcesz to sprzedać? Najpierw zajrzyj z drużyną do jakiegoś miasta!")
    return redirect(f"/dunnorpg/items/ch{kwargs['char_id']}")
@transaction.atomic
def give_item(request, **kwargs):
    from_char = get_object_or_404(models.Character, id=kwargs['from_char'])
    to_char = get_object_or_404(models.Character, id=kwargs['to_char'])
    raw_amount = str(kwargs['amount']).replace(",", ".")
    try:
        amount_decimal = Decimal(raw_amount)
    except InvalidOperation:
        messages.error(request, "Nieprawidlowa ilosc do transferu.")
        return redirect(f"/dunnorpg/items/ch{from_char.id}")

    if amount_decimal <= 0:
        messages.error(request, "Ilosc do transferu musi byc wieksza od 0.")
        return redirect(f"/dunnorpg/items/ch{from_char.id}")

    if (to_char.type or "").lower() != "player" and not request.user.is_superuser:
        messages.error(request, f"Cannot transfer to {to_char.name}.")
        return redirect(f"/dunnorpg/items/ch{from_char.id}")
    item_ref = str(kwargs["item_id"])
    if item_ref != "0":
        given_amount = int(amount_decimal.to_integral_value(rounding=ROUND_FLOOR))
        if given_amount < 1:
            messages.error(request, "Ilosc przedmiotow do transferu musi wynosic co najmniej 1.")
            return redirect(f"/dunnorpg/items/ch{from_char.id}")

        source_type = "eq"
        source_id = item_ref
        if "-" in item_ref:
            source_type, source_id = item_ref.split("-", 1)

        if not source_id.isdigit() or source_type not in {"eq", "char"}:
            messages.error(request, "Nieprawidlowy przedmiot do transferu.")
            return redirect(f"/dunnorpg/items/ch{from_char.id}")

        if source_type == "char":
            given_amount = 1
            char_item = get_object_or_404(models.CharItems, id=int(source_id), character=from_char.name)
            itemDesc = get_object_or_404(models.Items, name=char_item.name)
            if itemDesc.unobtainable:
                messages.error(request, f"{char_item.name} nie moze zostac przekazane.")
                return redirect(f"/dunnorpg/items/ch{from_char.id}")

            max_weight = get_character_max_weight(to_char)
            current_weight = get_character_current_weight(to_char)
            if not can_add_item_to_eq_by_limits(to_char, itemDesc, 1):
                messages.error(request, f"{to_char.name} moze miec maksymalnie {MAX_BAG_ITEMS_IN_EQ} torby w ekwipunku.")
                return redirect(f"/dunnorpg/items/ch{from_char.id}")

            if itemDesc.weight + current_weight <= max_weight:
                models.Eq.objects.create(
                    owner=to_char.owner,
                    character=to_char.name,
                    name=char_item.name,
                    type=itemDesc.type,
                    weight=itemDesc.weight,
                    durability=clamp_item_durability(itemDesc, char_item.durability),
                    amount=1,
                    additional_description=char_item.additional_description,
                    use_amount=char_item.use_amount,
                )

                delete_char_item(char_item)
                messages.success(request, f"Transferred {itemDesc.name} to {to_char.name}.")
            else:
                messages.error(request, f"Not enough space in {to_char.name} equipment.")
            return redirect(f"/dunnorpg/items/ch{from_char.id}")

        eq_item = get_object_or_404(models.Eq.objects.select_for_update(), id=int(source_id), character=from_char.name)
        if eq_item.book_trade_locked:
            messages.error(request, BOOK_TRADE_LOCKED)
            return redirect('items', char_id=from_char.id)
        itemDesc = get_object_or_404(models.Items, name=eq_item.name)
        if itemDesc.unobtainable:
            messages.error(request, f"{eq_item.name} nie moze zostac przekazane.")
            return redirect(f"/dunnorpg/items/ch{from_char.id}")

        if given_amount <= eq_item.amount:
            max_weight = get_character_max_weight(to_char)
            current_weight = get_character_current_weight(to_char)

            if not can_add_item_to_eq_by_limits(to_char, itemDesc, given_amount):
                messages.error(request, f"{to_char.name} moze miec maksymalnie {MAX_BAG_ITEMS_IN_EQ} torby w ekwipunku.")
                return redirect(f"/dunnorpg/items/ch{from_char.id}")

            if itemDesc.weight * given_amount + current_weight <= max_weight:
                models.Eq.objects.create(
                    owner=to_char.owner,
                    character=to_char.name,
                    name=eq_item.name,
                    type=eq_item.type,
                    weight=itemDesc.weight*given_amount,
                    durability=clamp_item_durability(itemDesc, eq_item.durability),
                    amount=given_amount,
                    additional_description=eq_item.additional_description,
                    use_amount=eq_item.use_amount,
                )

                messages.success(request, f"Transferred {eq_item.name} to {to_char.name}.")
                if given_amount >= eq_item.amount:
                    eq_item.delete()
                else:
                    eq_item.amount -= given_amount
                    eq_item.weight -= itemDesc.weight * given_amount
                    eq_item.save()
            else:
                messages.error(request, f"Not enough space in {to_char.name} equipment.")
        else:
            messages.error(request, f"Chcesz dać więcej niż masz? Linióweczka...")
    else:
        given_amount = float(amount_decimal)
        if from_char.coins>=given_amount:
            from_char.coins -= given_amount
            from_char.save()
            to_char.coins += given_amount
            to_char.save()
            messages.success(request, f"Transferred {given_amount} coins to {to_char.name}.")
        else:
            messages.error(request, f"{from_char.name} is too poor for that.")
    return redirect(f"/dunnorpg/items/ch{from_char.id}")

@require_POST
def move_hand_item_to_side(request, char_id, item_id):
    with transaction.atomic():
        char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
        if not request.user.is_authenticated or (not request.user.is_superuser and char.owner != request.user.username):
            return HttpResponse(status=403)

        item = get_object_or_404(
            models.CharItems.objects.select_for_update(),
            id=item_id, character=char.name,
        )
        if item.hand not in {"Left", "Right"} or item.position:
            messages.error(request, "Na pasek można przenieść tylko przedmiot trzymany w ręce.")
            return redirect('character_detail', char.id)

        item_desc = get_object_or_404(models.Items, name=item.name)
        if not is_weapon_item(item_desc):
            messages.error(request, "Na pasek można założyć tylko broń.")
            return redirect('character_detail', char.id)

        target_place = None
        for place in BELT_ITEM_PLACES:
            if get_equipped_item_for_place(char.name, place):
                continue
            can_equip, _ = can_equip_hand_item(char, item_desc, place)
            if can_equip:
                target_place = place
                break
        if target_place is None:
            messages.error(request, "Brak wolnych miejsc przy pasie. Broń dwuręczna wymaga dwóch wolnych miejsc.")
            return redirect('character_detail', char.id)

        item.hand = target_place
        item.save(update_fields=['hand'])
        sync_item_granted_skills(char)
    return redirect('character_detail', char.id)


@transaction.atomic
def swap_side_to_hand(request, **kwargs):
    char = get_object_or_404(models.Character.objects.select_for_update(), id=kwargs['char_id'])
    if not request.user.is_authenticated or (not request.user.is_superuser and char.owner != request.user.username):
        return HttpResponse(status=403)
    place = kwargs.get('place', 'Side').capitalize()
    hand = kwargs['hand'].capitalize()
    if place not in BELT_ITEM_PLACES or hand not in {"Left", "Right"}:
        return HttpResponse(status=404)
    side_item = get_object_or_404(models.CharItems, character=char.name, hand=place)
    side_desc = get_object_or_404(models.Items, name=side_item.name)
    to_swap = get_equipped_item_for_place(char.name, hand)
    if to_swap:
        to_swap_desc = get_object_or_404(models.Items, name=to_swap.name)
        can_equip, error = can_equip_hand_item(char, to_swap_desc, place)
        if not can_equip:
            messages.error(request, error)
            return redirect('character_detail', char.id)

    # Preserve moving the right-hand item to the backpack when drawing a two-handed weapon.
    right_item = get_equipped_item_for_place(char.name, "Right") if hand == "Left" else None
    right_desc = get_object_or_404(models.Items, name=right_item.name) if right_item else None
    stow_right = bool(side_desc.dualHanded and right_item and not can_pair_hand_items(char, side_desc, right_desc))
    if not stow_right:
        can_equip, error = can_equip_hand_item(char, side_desc, hand)
        if not can_equip:
            messages.error(request, error)
            return redirect('character_detail', char.id)
    if stow_right:
        models.Eq.objects.create(
            owner=char.owner, character=char.name, name=right_item.name,
            type=right_desc.type, weight=right_desc.weight,
            durability=clamp_item_durability(right_desc, right_item.durability),
            amount=1, additional_description=right_item.additional_description,
            use_amount=right_item.use_amount,
            reloaded=right_item.reloaded,
        )
        right_item.delete()
    if to_swap:
        to_swap.hand = place
        to_swap.save(update_fields=['hand'])
    side_item.hand = hand
    side_item.save(update_fields=['hand'])
    sync_item_granted_skills(char)
    return redirect('character_detail', char.id)


def change_item_durability(request,**kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    dur = request.POST.get('dur')
    if dur is None or dur == '':
        if is_partial_request(request):
            return JsonResponse({"error": "Wytrzymałość nie może być pusta."}, status=400)
        return redirect('character_detail', char.id)

    try:
        durability = int(dur)
    except ValueError:
        if is_partial_request(request):
            return JsonResponse({"error": "Wytrzymałość musi być liczbą całkowitą."}, status=400)
        return redirect('character_detail', char.id)

    item = get_object_or_404(models.CharItems, id=kwargs['item_id'])
    item.durability = durability
    item.save()

    if is_partial_request(request):
        item_desc = get_object_or_404(models.Items, name=item.name)
        max_durability = item_desc.maxDurability or 0
        durability_percent = "(0%)"
        if max_durability > 0:
            durability_percent = f"({item.durability / max_durability:.0%})"
        armor = 0
        if item_desc.armor != 0:
            armor = armor_by_durability(item_desc.armor, item.durability)
        block = 0
        if item_desc.block != 0:
            block = min(item_desc.block, math.ceil(item.durability / 50))
        return JsonResponse({
            "message": "Pomyślnie zmieniono wytrzymałość.",
            "durability": item.durability,
            "durability_percent": durability_percent,
            "armor": armor,
            "block": block,
        })

    return redirect('character_detail', char.id)


def get_city_repair_base_price(description, item):
    maximum = description.maxDurability or 0
    if maximum <= 0 or (description.type or '').strip().lower() == 'animal':
        return None
    durability = item.durability if item.durability is not None else maximum
    missing = maximum - max(0, durability)
    amount = item.amount if isinstance(item, models.Eq) else 1
    if missing <= 0 or amount <= 0:
        return None
    return (Decimal(str(description.price)) * Decimal('0.3') * Decimal(missing)
            / Decimal(maximum) * amount).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def get_city_character_charisma(character):
    charisma = character.CHAR + effect_stat_modifier(character, "CHAR") + sum(models.Mods.objects.filter(
        character=character.name, field='CHAR',
    ).values_list('value', flat=True))
    names = list(models.CharItems.objects.filter(character=character.name).values_list('name', flat=True))
    descriptions = {item.name: item for item in models.Items.objects.filter(name__in=names)}
    for name in names:
        description = descriptions.get(name)
        for stat in (description.skillStats or '').split(';') if description else []:
            if len(stat) >= 2 and stat[:-2].lower() == 'char':
                try:
                    charisma += int(stat[-2:])
                except ValueError:
                    pass
    return charisma


@require_POST
@transaction.atomic
def fix_item(request, **kwargs):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Zaloguj się, aby naprawiać przedmioty.'}, status=403)
    city = get_object_or_404(models.Cities.objects.select_for_update(), visiting=True)
    if not city.repair:
        return JsonResponse({'message': 'Naprawa nie jest dostępna w tym mieście.'}, status=403)
    try:
        data = json.loads(request.body)
        char_id = int(data['char_id'])
        item_id = int(data['item_id'])
        source = data['source']
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'message': 'Nieprawidłowe dane naprawy.'}, status=400)
    if source not in ('char', 'eq'):
        return JsonResponse({'message': 'Nieprawidłowe źródło przedmiotu.'}, status=400)
    characters = models.Character.objects.select_for_update().filter(hidden=False)
    if not request.user.is_superuser:
        characters = characters.filter(owner=request.user.username)
    character = get_object_or_404(characters, id=char_id)
    item_model = models.CharItems if source == 'char' else models.Eq
    item = get_object_or_404(item_model.objects.select_for_update(), id=item_id,
                             character=character.name, owner=character.owner)
    description = get_object_or_404(models.Items, name=item.name)
    base_cost = get_city_repair_base_price(description, item)
    if base_cost is None:
        return JsonResponse({'message': 'Ten przedmiot nie wymaga naprawy lub nie można go naprawić.'}, status=400)
    cost = get_city_healing_price(base_cost, get_city_character_charisma(character))
    coins = Decimal(str(character.coins))
    if coins < cost:
        return JsonResponse({'message': f'Za mało monet. Naprawa kosztuje {cost:g} monet. Brakuje {cost - coins:g} monet.'}, status=400)
    item.durability = description.maxDurability
    character.coins = float(coins - cost)
    item.save(update_fields=['durability'])
    character.save(update_fields=['coins'])
    return JsonResponse({
        'message': f'Naprawiono {item.name} do 100%. Koszt: {cost:g} monet.',
        'character_id': character.id, 'coins': character.coins,
        'new_durability': item.durability, 'cost': float(cost),
    })


def change_char_details(request, **kwargs):
    try:
        data = json.loads(request.body)
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        old_name = char.name
        new_name = (data.get('name') or old_name).strip()
        max_name_length = models.Character._meta.get_field("name").max_length

        if not new_name:
            raise ValueError("Nazwa postaci nie moze byc pusta")

        if len(new_name) > max_name_length:
            raise ValueError(f"Nazwa postaci moze miec maksymalnie {max_name_length} znakow")

        if models.Character.objects.filter(name=new_name).exclude(pk=char.pk).exists():
            raise ValueError("Postac o takiej nazwie juz istnieje")

        with transaction.atomic():
            if new_name != old_name:
                for related_model in [
                    models.Skills,
                    models.Eq,
                    models.CharItems,
                    models.Mods,
                    models.Effects,
                ]:
                    related_model.objects.filter(character=old_name).update(character=new_name)

            char.name = new_name
            char.fullHP = int(data['maxHP'])
            char.barrier = int(data['barrier'])
            char.points_left = int(data['points'])
            char.type = (data.get('type') or 'Player').strip() or 'Player'
            char.model_url = data['url']
            char.size = f"{float(data['size']):g}"
            char.save()

        return JsonResponse({"message": "Pomyslnie zmieniono dane", "name": char.name}, status=200)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=400)
    
@require_POST
@transaction.atomic
def end_round_infight(request, char_id):
    char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
        return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)

    effects = list(active_effects(char))
    rolls, actions_left, hp_changes, mobility_modifier = round_effects(effects)
    required_fields = {roll['field'] for roll in rolls}
    submitted_fields = {field for field in request.POST if field.startswith('effect_roll_')}
    try:
        if required_fields != submitted_fields:
            raise ValueError
        values = [int(request.POST[roll['field']]) for roll in rolls]
        if any(not 1 <= value <= roll['sides'] for roll, value in zip(rolls, values)):
            raise ValueError
    except ValueError:
        return JsonResponse({
            'error': 'Podaj prawidłowe wyniki rzutów dla aktualnych efektów.',
            'rolls': rolls,
        }, status=409)

    char.actionLeft = actions_left
    char.round_mobility_bonus = mobility_modifier
    hp_before = char.HP
    damage_handler = calculateGettingHit()
    if char.deferred_damage:
        damage = char.deferred_damage
        char.deferred_damage = 0
        damage_handler.apply_damage(char, damage, ('head', 'torso', 'hands', 'legs'), max(0, char.barrier))
    for roll, value in zip(rolls, values):
        damage_handler.apply_damage(
            char, value, ('head', 'torso', 'hands', 'legs'),
            max(0, char.barrier), ignore_armor=roll['ignore_armor'],
        )
    for amount in hp_changes:
        char.HP = max(0, char.HP + amount)
        if amount > 0 and char.fullHP is not None:
            char.HP = min(char.HP, char.fullHP)
    char.save(update_fields=['actionLeft', 'HP', 'round_mobility_bonus', 'deferred_damage'])

    for effect in effects:
        if effect.name == READ_BOOKS_EFFECT:
            continue
        if effect.time <= 1:
            effect.delete()
        elif effect.time < 100:
            effect.time -= 1
            effect.save(update_fields=['time'])

    for mod in models.Mods.objects.filter(owner=char.owner, character=char.name, time__gt=0):
        if mod.time == 1:
            mod.delete()
        else:
            mod.time -= 1
            mod.save(update_fields=['time'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'hp': char.HP, 'barrier': char.barrier, 'hp_lost': max(0, hp_before - char.HP)})
    return redirect('character_detail', char.id)


@require_POST
@transaction.atomic
def add_character_effect(request, char_id):
    char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
        return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)

    try:
        effect_id = int(request.POST.get('effect', ''))
        time = int(request.POST.get('time', ''))
        if time < 1 or time > 1000:
            raise ValueError
    except ValueError:
        messages.error(request, 'Wybierz efekt i podaj czas od 1 do 1000 rund.')
        return redirect('character_detail', char.id)

    effect = get_object_or_404(models.Effects_Decs, pk=effect_id)
    effect = add_active_effect(char.owner, char.name, effect.name, time, request.POST.get('desc', '').strip())
    messages.success(request, f'Dodano efekt {effect.name}.')
    return redirect('character_detail', char.id)


@require_POST
@transaction.atomic
def change_character_effect_time(request, char_id, effect_id):
    char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
        return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)

    effect = get_object_or_404(models.Effects, pk=effect_id, owner=char.owner, character=char.name)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if effect.name == READ_BOOKS_EFFECT:
        message = 'Historia przeczytanych książek jest trwała.'
        if is_ajax:
            return JsonResponse({'error': message}, status=403)
        messages.error(request, message)
        return redirect('character_detail', char.id)

    try:
        time = int(request.POST.get('time', ''))
        if not 1 <= time <= 1000:
            raise ValueError
    except ValueError:
        message = 'Podaj czas od 1 do 1000 rund.'
        if is_ajax:
            return JsonResponse({'error': message}, status=400)
        messages.error(request, message)
        return redirect('character_detail', char.id)

    effect.time = time
    effect.save(update_fields=['time'])
    if is_ajax:
        return JsonResponse({'time': effect.time})
    return redirect('character_detail', char.id)


@require_POST
@transaction.atomic
def remove_character_effect(request, char_id, effect_id):
    char = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
    if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
        return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)

    effect = get_object_or_404(models.Effects, pk=effect_id, owner=char.owner, character=char.name)
    if effect.name == READ_BOOKS_EFFECT:
        message = 'Nie można usunąć historii przeczytanych książek.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': message}, status=403)
        messages.error(request, message)
        return redirect('character_detail', char.id)
    effect.delete()
    messages.success(request, f'Usunięto efekt {effect.name}.')
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
        try:
            action_left = float(request.POST['actions-amount'])
        except (TypeError, ValueError):
            msg = "Nieprawidłowa ilość akcji."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])

        if action_left < 0:
            msg = "Ilość akcji nie może być mniejsza niż 0."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect('character_detail', kwargs['char_id'])

        char.actionLeft = action_left
        char.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                "actionLeft": char.actionLeft,
                "message": "Pomyślnie zmieniono ilość akcji.",
            })
        return redirect('character_detail', char.id) 

def change_counter(request, **kwargs):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    counter_field = kwargs.get('counter_field')
    fields = {
        "counter": ("counter", "counterName"),
        "counter2": ("counter2", "counterName2"),
        "advantageBalance": ("advantageBalance", None),
    }

    if counter_field not in fields:
        return JsonResponse({"error": "Nieprawidłowy licznik."}, status=400)

    try:
        char = get_object_or_404(models.Character, id=kwargs['char_id'])
        value_raw = request.POST.get(counter_field, '').strip()
        if not re.match(r'^-?\d+$', value_raw):
            raise ValueError("Licznik musi być liczbą całkowitą większą lub równą 0")

        value = int(value_raw)
        if counter_field != "advantageBalance" and value < 0:
            raise ValueError("Licznik musi byc liczba calkowita wieksza lub rowna 0")

        value_field, name_field = fields[counter_field]
        counter_name = getattr(char, name_field) if name_field else "Bilans Przewag"
        counter_name = counter_name or "Licznik"
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

            value = int(request.POST[f'{stat_type}-amount'])
            msg = ""
            msg_type = "success"

            with transaction.atomic():
                char = get_object_or_404(models.Character.objects.select_for_update(), id=kwargs['char_id'])
                if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
                    return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
                if stat_type == "alcohol":
                    previous_alcohol_level = char.alcohol
                    value = max(0, value)
                    char.alcohol = value
                    char.save(update_fields=['alcohol'])
                    sync_alcohol_effects(char, previous_alcohol_level)
                else:
                    value = max(0, min(100, value))
                    current_value = getattr(char, stat_type)
                    char, msg = manageFoodAndWater(char, value - current_value, stat_type)
                    char.save(update_fields=[stat_type, 'HP'])

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
                    "effects_html": render_to_string(
                        "dunnorpg/character_effects_block.html",
                        {
                            "character": char,
                            "effect_definitions": models.Effects_Decs.objects.order_by('name'),
                        },
                        request=request,
                    ),
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

def count_hp_level_change(previous_level, current_level):
    return current_level // 5 - previous_level // 5

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
        previous_level = char.level
        total_exp = max(0, ((previous_level - 1) * 100) + int(char.exp) + amount)
        char.level = (total_exp // 100) + 1
        char.exp = total_exp % 100
        level_change = char.level - previous_level
        hp_change = count_hp_level_change(previous_level, char.level)

        if level_change > 0:
            char.points_left = (char.points_left or 0) + level_change
            if hp_change > 0:
                char.fullHP = (char.fullHP or 0) + hp_change
                char.HP += hp_change
            if not is_player_animal(char):
                char, waterMessage = manageFoodAndWater(char, -20*level_change, "water")
                char, foodMessage = manageFoodAndWater(char, -20*level_change, "food")
            msg = f"Zdobyto poziom! Nowy poziom to {char.level}, otrzymano {level_change} punktów umiejętności."
            if hp_change > 0:
                msg += f" Punkty Życia zwiększone o {hp_change}."
            if waterMessage != "":
                msg += f" {waterMessage}"
            if foodMessage != "":
                msg += f" {foodMessage}"
        elif level_change < 0:
            levels_lost = abs(level_change)
            char.points_left = max(0, (char.points_left or 0) - levels_lost)
            hp_lost = abs(hp_change)
            if hp_lost > 0:
                char.fullHP = max(0, (char.fullHP or 0) - hp_lost)
                char.HP = max(0, min(char.HP - hp_lost, char.fullHP))
            msg = f"Liczba utraconych poziomów: {levels_lost}. Nowy poziom to {char.level}, pozostało {char.exp}% doświadczenia."
            if hp_lost > 0:
                msg += f" Punkty Życia zmniejszone o {hp_lost}."
        else:
            if amount >= 0:
                msg = f"Dodano {amount} doświadczenia, łącznie masz już {char.exp}% doświadczenia"
            else:
                msg = f"Zabrano {abs(amount)} doświadczenia, pozostało ci {char.exp}% doświadczenia"

        char.save()

    except Exception as e:
        msg = f"Błąd: {e}"
        msg_type = 'error'
        print(traceback.format_exc())

    return char, msg, msg_type

def add_exp(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    exp = kwargs['exp']

    char, msg, msg_type = manageExp(char, exp)

    if msg_type == 'error':
        messages.error(request, f"{char.name}: {msg}")
    else:
        messages.success(request, f"{char.name}: {msg}")

    selected_animal_ids = [
        animal_id for animal_id in request.GET.getlist('exp_animals')
        if str(animal_id).isdigit()
    ]
    selected_animals = models.Character.objects.filter(
        id__in=selected_animal_ids,
        owner=char.owner,
        type__iexact="Gracz: Zwierze",
        hidden=False,
    ).exclude(id=char.id)

    for animal in selected_animals:
        animal, animal_msg, animal_msg_type = manageExp(animal, exp)
        if animal_msg_type == 'error':
            messages.error(request, f"{animal.name}: {animal_msg}")
        else:
            messages.success(request, f"{animal.name}: {animal_msg}")

    return redirect('character_detail', char.id)

def char_wear_item(request, **kwargs):
    char = get_object_or_404(models.Character, id=kwargs['char_id'])
    char_skills = models.Skills.objects.filter(character=char.name)
    place = kwargs['place'] #hand or position
    item_id = kwargs['item_id']
    item_eq_obj = models.Eq.objects.get(character=char.name,id=item_id)
    item = models.Items.objects.get(name=item_eq_obj.name)
    item_category = (item.category or "").lower()

    if (item.type or '').strip().casefold() == BOOK_TYPE:
        messages.error(request, 'Książkę można przeczytać w ekwipunku.')
        return redirect('character_detail', char.id)

    if place.lower() in HAND_ITEM_PLACES and not is_weapon_item(item):
        messages.error(request, "W tym slocie mozna zalozyc tylko bron.")
        return redirect('character_detail', char.id)

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

    if is_character_accessory_position(place) and not is_character_accessory_item(item):
        messages.error(request, "W tym slocie mozna zalozyc tylko akcesoria.")
        return redirect('character_detail', char.id)

    if place == "Amulet" and (item.type != "Amulet" or is_character_accessory_item(item)):
        messages.error(request, "W tym slocie mozna zalozyc tylko amulet.")
        return redirect('character_detail', char.id)

    can_wear_armor, armor_weight_message = can_character_wear_armor_weight(char, item, place)
    if not can_wear_armor:
        messages.error(request, armor_weight_message)
        return redirect('character_detail', char.id)
    
    can_equip_hand, hand_message = can_equip_hand_item(char, item, place)
    if not can_equip_hand:
        messages.error(request, hand_message)
        return redirect('character_detail', char.id)

    # TODO: If Wojskowe przeszkolenie is level 1, add an attack and parry penalty for the polearm.

        
            
    charItObj = get_equipped_item_for_place(char.name, place)
    if charItObj == None: 
        if place.lower() in HAND_ITEM_PLACES:
            models.CharItems.objects.create(
                owner = char.owner,
                character = char.name,
                name = item.name,
                durability = clamp_item_durability(item, item_eq_obj.durability),
                hand = place.capitalize(),
                position = '',
                additional_description = item_eq_obj.additional_description,
                use_amount = item_eq_obj.use_amount,
                reloaded = item_eq_obj.reloaded,
                )
        else:
            models.CharItems.objects.create(
                owner = char.owner,
                character = char.name,
                name = item.name,
                durability = clamp_item_durability(item, item_eq_obj.durability),
                hand = '',
                position = place.capitalize(),
                additional_description = item_eq_obj.additional_description,
                use_amount = item_eq_obj.use_amount,
                reloaded = item_eq_obj.reloaded,
                )            
    else:
        charItObj.owner = char.owner
        charItObj.name = item.name
        charItObj.durability = clamp_item_durability(item, item_eq_obj.durability)
        charItObj.additional_description = item_eq_obj.additional_description
        charItObj.use_amount = item_eq_obj.use_amount
        charItObj.reloaded = item_eq_obj.reloaded
        charItObj.save()  

    if item.skillEffects != None:
        for effect in item.skillEffects.split(';'):
            effect = effect.split("-")

            add_active_effect(char.owner, char.name, effect[0], effect[2], refresh_time=100)

    sync_item_granted_skills(char)

    if item_eq_obj.amount == 1:
        item_eq_obj.delete()
    else:
        item_eq_obj.weight -= item.weight
        item_eq_obj.amount -= 1
        item_eq_obj.save()
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

@user_passes_test(lambda u: u.is_superuser)
def reset_portal(request):
    if request.method != 'POST':
        return redirect('gm_panel')

    players = models.Character.objects.filter(hidden=False, type__iexact='Player')
    player_names = list(players.values_list('name', flat=True))
    player_count = len(player_names)

    with transaction.atomic():
        players.update(mutation="")
        deleted_eq_count, _ = models.Eq.objects.filter(character__in=player_names).delete()
        deleted_char_items_count, _ = models.CharItems.objects.filter(character__in=player_names).delete()
        models.Skills.objects.filter(character__in=player_names).filter(Q(source="item") | Q(source__startswith="item:")).delete()
        reset_skills_count = models.Skills.objects.filter(character__in=player_names).update(uses_left=0)

    messages.warning(
        request,
        (
            f"Reset portalowy wykonany dla {player_count} postaci. "
            f"Usunięto {deleted_eq_count} przedmiotów z eq, "
            f"{deleted_char_items_count} założonych przedmiotów i "
            f"wyzerowano {reset_skills_count} ładunków skilli."
        )
    )
    return redirect('gm_panel')

def update_field(request, **kwargs):
    text = request.POST.get('notes-text')
    field_id = request.POST.get('id')
    model = request.POST.get('model')
    
    if model == "Character":
        obj = get_object_or_404(models.Character, id=field_id)
        obj.notes = text
        obj.save(update_fields=["notes"])
        if is_partial_request(request):
            return JsonResponse({"message": "Notatki zapisane."})
    elif is_partial_request(request):
        return JsonResponse({"error": "Nieprawidłowy model notatek."}, status=400)
    
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
    if (it2D.type or '').strip().casefold() == BOOK_TYPE:
        messages.error(request, 'Książkę można przeczytać w ekwipunku.')
        return redirect('character_detail', char.id)

    armor_place = it1.position or it1.hand
    if (armor_place or "").lower() in HAND_ITEM_PLACES and not is_weapon_item(it2D):
        messages.error(request, "W tym slocie mozna zalozyc tylko bron.")
        return redirect('character_detail', char.id)

    if armor_place in MOUNT_ATTACHMENT_POSITIONS:
        if not models.CharItems.objects.filter(character=char.name, position="Mount").exists():
            messages.error(request, "Najpierw załóż wierzchowca.")
            return redirect('character_detail', char.id)

        allowed_categories = MOUNT_ATTACHMENT_CATEGORIES.get(armor_place, set())
        if (it2D.category or "").lower() not in allowed_categories and not (armor_place == "Mount_armor" and it2D.type == "Mount Armor"):
            messages.error(request, "Ten przedmiot nie pasuje do wybranego slotu wierzchowca.")
            return redirect('character_detail', char.id)

    if is_character_accessory_position(armor_place) and not is_character_accessory_item(it2D):
        messages.error(request, "W tym slocie mozna zalozyc tylko akcesoria.")
        return redirect('character_detail', char.id)

    if armor_place == "Amulet" and (it2D.type != "Amulet" or is_character_accessory_item(it2D)):
        messages.error(request, "W tym slocie mozna zalozyc tylko amulet.")
        return redirect('character_detail', char.id)

    can_wear_armor, armor_weight_message = can_character_wear_armor_weight(char, it2D, armor_place)
    if not can_wear_armor:
        messages.error(request, armor_weight_message)
        return redirect('character_detail', char.id)

    can_equip_hand, hand_message = can_equip_hand_item(char, it2D, armor_place)
    if not can_equip_hand:
        messages.error(request, hand_message)
        return redirect('character_detail', char.id)

    # TODO: If Wojskowe przeszkolenie is level 1, add an attack and parry penalty for the polearm.

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
        durability=clamp_item_durability(it1D, it1.durability),
        additional_description=it1.additional_description,
        use_amount=it1.use_amount,
        reloaded=it1.reloaded,
    )

    if it1D.skillEffects != None:
        for effect in it1D.skillEffects.split(';'):
            effect = effect.split("-")
            models.Effects.objects.filter(character=char.name, name=effect[0]).first().delete()
    
    it1.name = it2.name
    it1.durability = it2.durability
    it1.additional_description = it2.additional_description
    it1.use_amount = it2.use_amount
    it1.reloaded = it2.reloaded
    it1.save()

    if it2D.skillEffects != None:
        for effect in it2D.skillEffects.split(';'):
            effect = effect.split("-")

            add_active_effect(char.owner, char.name, effect[0], effect[2])
    
    it2.delete()
    sync_item_granted_skills(char)
    
    return redirect('character_detail', char.id)
@user_passes_test(lambda u: u.is_superuser)
def end_round(request, **kwargs):
    msg = 'Deleted: '
    for effect in models.Effects.objects.exclude(name=READ_BOOKS_EFFECT):
        if effect.time < 100:
            effect.time -= 1
            if effect.time <= 0:
                msg += f"{effect.character}-{effect.name}; "
                effect.delete()
            else:
                effect.save()
    for mod in models.Mods.objects.filter(time__gt=0):
        mod.time -= 1
        if mod.time <= 0:
            msg += f"{mod.character}-{mod.field}; "
            mod.delete()
        else:
            mod.save()
    if msg != 'Deleted: ':
        messages.warning(request, msg)
    return redirect('gm_panel')

def manageFoodAndWater(char, value, stat_type):  # stat_type: "food" or "water"
    effects = models.Effects.objects.filter(owner=char.owner, character=char.name)
    condition = {"food": "Głód", "water": "Pragnienie"}[stat_type]
    effect_name = "Utrudnienie"
    description = f"Odczuwasz {condition}"
    condition_effects = effects.filter(name=effect_name, desc=description)
    value_now = getattr(char, stat_type)
    value_changed = value_now + value
    setattr(char, stat_type, min(100, max(0, value_changed)))

    if value_changed > 20:
        if value_now <= 20:
            condition_effects.delete()
        return char, ""

    if (
        not condition_effects.exists()
        and effects.filter(name="DużeUtrudnienie").count() < maxBigAdvs
        and effects.filter(name=effect_name).count() < maxAdvs
    ):
        models.Effects.objects.create(owner=char.owner, character=char.name, name=effect_name, desc=description, time=1000)

    msg = f"Odczuwasz {condition}"
    if value_changed < 0:
        lost_hp = -value_changed
        char.HP = max(0, char.HP - lost_hp)
        msg += f" i tracisz {lost_hp} PŻ"
    return char, msg


class ItemsView(ListView):
    model = models.Items
    template_name = 'items.html'
    context_object_name = 'items'
    ordering = ['name']

    def get_template_names(self):
        if self.kwargs['char_id'] == 0 and is_partial_request(self.request):
            return ['dunnorpg/items_results.html']
        return [self.template_name]

    @staticmethod
    def sort_items_by_name(items):
        return sorted(items, key=lambda item: (item.get('name') or '').lower())
    
    def get_queryset(self):
        queryset = []
        value = (self.request.GET.get('search') or '').strip()
        selected_type = (self.request.GET.get('item_type') or '').strip()
        selected_category = (self.request.GET.get('item_category') or '').strip()
        char_id = self.kwargs['char_id']
        if char_id != 0:
            self.character = models.Character.objects.filter(id=char_id).first()
        else:
            self.character = None

        if self.character == None:
            if value or selected_type or selected_category:
                queryset = models.Items.objects.all()
                if not self.request.user.is_superuser:
                    queryset = queryset.filter(found=True)
                if value:
                    queryset = queryset.filter(Q(name__icontains=value) | Q(desc__icontains=value))
                if selected_type:
                    queryset = queryset.filter(type=selected_type)
                if selected_category:
                    queryset = queryset.filter(category=selected_category)
                queryset = queryset.order_by(Lower('name'))
        else:
            self.singlehand = []
            self.twohand = []
            self.gunpowder = []
            self.animals = []
            self.armor_dict = {'helmet': [], 'torso': [], 'boots': [], 'gloves': [], 'amulets': [], 'accessories': [], 'ammo': [], 'other': []}

            def add_character_item(
                item_desc,
                durability,
                amount=1,
                eq_id=None,
                char_item_id=None,
                equipped=False,
                inventory_weight=None,
                use_amount=None,
                book_trade_locked=False,
            ):
                display_weight = inventory_weight if inventory_weight is not None else item_desc.weight * amount
                item_data = {
                    'id': item_desc.id,
                    'eq_id': eq_id,
                    'char_item_id': char_item_id,
                    'delete_id': f"char-{char_item_id}" if equipped else f"eq-{eq_id}",
                    'sell_id': f"char-{char_item_id}" if equipped else eq_id,
                    'rarity': item_desc.rarity,
                    'found': item_desc.found,
                    'name': item_desc.name,
                    'desc': item_desc.desc,
                    'dur': durability,
                    'amount': amount,
                    'weight': display_weight,
                    'max_dur': item_desc.maxDurability,
                    'type': item_desc.type,
                    'price': item_desc.price,
                    'on_use': item_desc.on_use,
                    'is_book': (item_desc.type or '').strip().casefold() == BOOK_TYPE,
                    'book_trade_locked': book_trade_locked,
                    'use_cost': item_desc.use_cost,
                    'use_info': item_desc.use_info,
                    'use_amount': use_amount,
                    'equipped': equipped,
                }
                queryset.append(item_data)

                category_data = item_desc.__dict__ | {
                    'is_book': item_data['is_book'],
                    'book_trade_locked': book_trade_locked,
                    'use_amount': item_data['use_amount'],
                    'dur': durability,
                    'amount': amount,
                    'weight': display_weight,
                    'max_dur': item_desc.maxDurability,
                    'eq_id': eq_id,
                    'char_item_id': char_item_id,
                    'delete_id': f"char-{char_item_id}" if equipped else f"eq-{eq_id}",
                    'sell_id': f"char-{char_item_id}" if equipped else eq_id,
                    'equipped': equipped,
                }
                armor_category = {
                    'helmet': 'helmet',
                    'torso': 'torso',
                    'boots': 'boots',
                    'gloves': 'gloves',
                    'amulet': 'amulets',
                    'accessory': 'accessories',
                    'akcesoria': 'accessories',
                    'amunicja': 'ammo',
                    'other': 'other',
                }.get(item_desc.type.lower())
                item_category = (item_desc.category or "").strip().lower()
                if item_category == 'gunpowder_item':
                    self.gunpowder.append(category_data)
                elif 'weapon_' in item_category or item_category == 'shield':
                    (self.twohand if item_desc.dualHanded else self.singlehand).append(category_data)
                elif armor_category:
                    self.armor_dict[armor_category].append(category_data)
                else:
                    if item_desc.type == 'Animal' or item_desc.type == 'Mount Armor' or (item_desc.category or "").lower() in MOUNT_ITEM_CATEGORIES:
                        self.animals.append(category_data)
                    elif is_weapon_item(item_desc) and item_desc.dualHanded == False:
                        self.singlehand.append(category_data)
                    elif is_weapon_item(item_desc):
                        self.twohand.append(category_data)
                    else:
                        self.armor_dict['other'].append(category_data)

            for item in models.Eq.objects.filter(character=self.character.name):
                item_obj = get_object_or_404(models.Items, name=item.name)
                add_character_item(
                    item_obj,
                    item.durability,
                    item.amount,
                    item.id,
                    inventory_weight=item.weight,
                    use_amount=item.use_amount,
                    book_trade_locked=item.book_trade_locked,
                )

            for item in models.CharItems.objects.filter(character=self.character.name):
                if item.name:
                    item_obj = get_object_or_404(models.Items, name=item.name)
                    add_character_item(
                        item_obj,
                        item.durability,
                        char_item_id=item.id,
                        equipped=True,
                        inventory_weight=item_obj.weight,
                        use_amount=item.use_amount,
                    )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_value'] = self.request.GET.get('search', '')
        context['selected_item_type'] = self.request.GET.get('item_type', '')
        context['selected_item_category'] = self.request.GET.get('item_category', '')

        item_types_queryset = models.Items.objects.exclude(type__isnull=True).exclude(type='')
        if not self.request.user.is_superuser:
            item_types_queryset = item_types_queryset.filter(found=True)
        context['item_types'] = sorted(
            set(item_types_queryset.values_list('type', flat=True)),
            key=lambda item_type: item_type.lower()
        )
        item_categories_queryset = models.Items.objects.exclude(category__isnull=True).exclude(category='')
        if not self.request.user.is_superuser:
            item_categories_queryset = item_categories_queryset.filter(found=True)
        context['item_categories'] = sorted(
            set(item_categories_queryset.values_list('category', flat=True)),
            key=lambda item_category: item_category.lower()
        )
        
        names = ['items_helmet','items_torso','items_boots','items_gloves','items_amulets','items_accessories','items_ammo','items_other']
        types = ['Helmet','Torso','Boots','Gloves','Amulet','Accessory','Amunicja','Other']
        
        if self.character == None:
            visible_items = models.Items.objects.all()
            if not self.request.user.is_superuser:
                visible_items = visible_items.filter(found=True)
            weapons = visible_items.filter(Q(category__icontains='weapon_') | Q(category__iexact='shield'))
            context['items_singlehand'] = weapons.filter(dualHanded=False).order_by(Lower('name'))
            context['items_twohand'] = weapons.filter(dualHanded=True).order_by(Lower('name'))
            context['items_gunpowder'] = visible_items.filter(category__iexact='gunpowder_item').order_by(Lower('name'))
            context['animals'] = visible_items.filter(
                Q(type='Animal') | Q(type='Mount Armor') | Q(category__in=MOUNT_ITEM_CATEGORIES)
            ).order_by(Lower('name'))
            
            for x in range(len(names)):
                if self.request.user.is_superuser:
                    if names[x] == 'items_accessories':
                        context[names[x]] = models.Items.objects.filter(Q(type='Accessory') | Q(type='Akcesoria')).order_by(Lower('name'))
                    elif names[x] == 'items_ammo':
                        context[names[x]] = models.Items.objects.filter(type__iexact='Amunicja').order_by(Lower('name'))
                    else:
                        context[names[x]] = models.Items.objects.filter(type=types[x]).order_by(Lower('name'))
                else:
                    if names[x] == 'items_accessories':
                        context[names[x]] = models.Items.objects.filter(Q(type='Accessory') | Q(type='Akcesoria'), found=True).order_by(Lower('name'))
                    elif names[x] == 'items_ammo':
                        context[names[x]] = models.Items.objects.filter(type__iexact='Amunicja', found=True).order_by(Lower('name'))
                    else:
                        context[names[x]] = models.Items.objects.filter(type=types[x], found=True).order_by(Lower('name'))
        else:
            
            items_weight = get_character_current_weight(self.character)
            max_weight = get_character_max_weight(self.character)
            
            charisma = self.character.CHAR + effect_stat_modifier(self.character, "CHAR")
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
            context['items_singlehand'] = self.sort_items_by_name(self.singlehand)
            context['items_twohand'] = self.sort_items_by_name(self.twohand)
            context['items_gunpowder'] = self.sort_items_by_name(self.gunpowder)
            context['animals'] = self.sort_items_by_name(self.animals)
            context['items_helmet'] = self.sort_items_by_name(self.armor_dict['helmet'])
            context['items_torso'] = self.sort_items_by_name(self.armor_dict['torso'])
            context['items_gloves'] = self.sort_items_by_name(self.armor_dict['gloves'])
            context['items_boots'] = self.sort_items_by_name(self.armor_dict['boots'])
            context['items_amulets'] = self.sort_items_by_name(self.armor_dict['amulets'])
            context['items_accessories'] = self.sort_items_by_name(self.armor_dict['accessories'])
            context['items_ammo'] = self.sort_items_by_name(self.armor_dict['ammo'])
            context['items_other'] = self.sort_items_by_name(self.armor_dict['other'])
            context['all_items'] = models.Items.objects.order_by('name')
            player_items = models.Eq.objects.filter(character=self.character.name)
            context['reading_book'] = current_reading_book(player_items.filter(owner=self.character.owner))
            equipped_items = models.CharItems.objects.filter(character=self.character.name).exclude(name__isnull=True).exclude(name='')
            unobtainable_item_names = models.Items.objects.filter(unobtainable=True).values_list('name', flat=True)
            player_items = list(player_items.filter(book_trade_locked=False).exclude(name__in=unobtainable_item_names))
            equipped_items = list(equipped_items.exclude(name__in=unobtainable_item_names))
            equipped_item_weights = dict(
                models.Items.objects.filter(name__in={item.name for item in equipped_items}).values_list('name', 'weight')
            )
            transfer_items = [
                {
                    "transfer_id": f"eq-{item.id}",
                    "name": item.name,
                    "durability": item.durability,
                    "amount": item.amount,
                    "weight": item.weight,
                    "equipped": False,
                }
                for item in player_items
            ]
            transfer_items += [
                {
                    "transfer_id": f"char-{item.id}",
                    "name": item.name,
                    "durability": item.durability,
                    "amount": 1,
                    "weight": equipped_item_weights.get(item.name, 0),
                    "equipped": True,
                }
                for item in equipped_items
            ]
            context['transfer_items'] = sorted(transfer_items, key=lambda item: (item["name"] or "").lower())
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
        inventory_return_character_id = None
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
                item.use_amount = referenced_item.use_amount
                inventory_character = models.Character.objects.filter(
                    owner=referenced_item.owner,
                    name=referenced_item.character
                ).first()
                if inventory_character:
                    inventory_return_character_id = inventory_character.id
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
        context['inventory_return_character_id'] = inventory_return_character_id

        return context

def learn_book_skills(character, book):
    targets = book_skill_targets(parse_item_granted_skills(book.grantedSkills))
    if not targets:
        raise ValueError('Ta książka nie ma przypisanej umiejętności.')

    category = (book.category or '').strip().casefold()
    if category not in {'podręcznik', ADVANCED_BOOK_CATEGORY, GRIMOIRE_CATEGORY}:
        raise ValueError('Ta książka nie ma poprawnej kategorii.')
    if category == GRIMOIRE_CATEGORY and not magical_classes([character.chosen_class]).exists():
        raise ValueError('Grymuar może przeczytać tylko postać z klasy z kategorii Magiczne.')

    definitions = {}
    for details in models.Skills_Decs.objects.order_by('pk'):
        if details.name.casefold() in targets:
            definitions.setdefault(details.name.casefold(), details)
    allowed_ids = set()
    if category == ADVANCED_BOOK_CATEGORY:
        allowed_ids = set(skills_available_in_editor(character.chosen_class).values_list('id', flat=True))
    skills = {}
    for skill in permanent_skills().filter(owner=character.owner, character=character.name).order_by('pk'):
        skills.setdefault(skill.skill.casefold(), skill)

    learned = []
    for key, (_, level) in targets.items():
        details = definitions.get(key)
        description = getattr(details, f'level{level}', None)
        if not description:
            raise ValueError(f'Książka zawiera nieprawidłową umiejętność lub poziom: {key}, poz. {level}.')
        if category == ADVANCED_BOOK_CATEGORY and details.pk not in allowed_ids:
            raise ValueError(f'{details.name} nie jest dostępna w edycji tej postaci.')

        skill = skills.get(key)
        current_level = (skill.level or 0) if skill else 0
        error = book_previous_level_error(details.name, level, current_level)
        if error:
            raise ValueError(error)
        if current_level >= level:
            continue
        error = skill_requirement_error(character, details, level)
        if error:
            raise ValueError(error)

        if skill is None:
            skill = models.Skills(
                owner=character.owner, character=character.name, skill=details.name,
                category=details.category,
            )
        skill.level = level
        skill.source = f'book:{level}'
        skill.desc = f'{details.desc} {description}'
        skill.uses_left = getattr(details, f'useslvl{level}') or 0
        skill.save()
        learned.append(f'{details.name} (poz. {level})')

    if not learned:
        raise ValueError('Postać zna już umiejętności z tej książki na tym samym lub wyższym poziomie.')

    sync_item_granted_skills(character)
    effects = models.Effects.objects.filter(owner=character.owner, character=character.name, name=READ_BOOKS_EFFECT)
    effect = effects.order_by('pk').first()
    if effect is None:
        effects.create(owner=character.owner, character=character.name, name=READ_BOOKS_EFFECT, desc=book.name, time=1000)
    else:
        titles = effect.desc.splitlines()
        if book.name not in titles:
            titles.append(book.name)
        effect.desc = '\n'.join(titles)
        effect.time = 1000
        effect.save(update_fields=['desc', 'time'])
    return learned


class useItem(APIView):
    def post(self, request, id, char_id):
        book = get_object_or_404(models.Items, id=id, type__iexact=BOOK_TYPE)
        try:
            with transaction.atomic():
                character = get_object_or_404(models.Character.objects.select_for_update(), id=char_id)
                if not request.user.is_authenticated or (character.owner != request.user.username and not request.user.is_superuser):
                    return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
                # A chapter change and a reading must take effect in a definite order.
                models.GameSettings.objects.select_for_update().get(pk=get_game_settings().pk)
                inventory = models.Eq.objects.filter(owner=character.owner, character=character.name)
                reading_book = current_reading_book(inventory)
                if reading_book:
                    raise ValueError(f'Postać czyta już „{reading_book}”. Kolejną książkę można zacząć po zmianie rozdziału.')
                copies = inventory.select_for_update().filter(
                    name=book.name, amount__gt=0,
                )
                eq_id = request.POST.get('eq_id')
                copy = get_object_or_404(copies, pk=eq_id) if eq_id else copies.order_by('pk').first()
                if copy is None:
                    raise Http404

                cost = float(book.use_cost) if character.inFight and book.use_cost not in (None, '', '-') else 0
                if not math.isfinite(cost) or cost < 0:
                    raise ValueError('Książka ma nieprawidłowy koszt użycia.')
                if cost and character.actionLeft < cost:
                    raise ValueError(f'Za mało akcji, aby przeczytać książkę. Potrzeba {cost}.')
                learned = learn_book_skills(character, book)

                if cost:
                    character.actionLeft -= cost
                    character.save(update_fields=['actionLeft'])
                if copy.amount > 1:
                    unit_weight = (copy.weight / copy.amount).quantize(Decimal('0.1'))
                    copy_model_instance(
                        copy, amount=copy.amount - 1, weight=copy.weight - unit_weight,
                    )
                    copy.amount = 1
                    copy.weight = unit_weight
                copy.book_trade_locked = True
                copy.save(update_fields=['amount', 'weight', 'book_trade_locked'])
            messages.success(request, f'Przeczytano „{book.name}”. Umiejętności: {", ".join(learned)}.')
        except ValueError as error:
            messages.error(request, str(error))
        return redirect('items', char_id=char_id)

    def get(self, request, *args, **kwargs):
        try:
            item_id = kwargs['id']
            item = get_object_or_404(models.Items, id=item_id)
            if (item.type or '').strip().casefold() == BOOK_TYPE:
                return HttpResponseNotAllowed(['POST'])
            action = item.on_use
            actions = [part.strip() for part in action.split(";") if part.strip()]
            cost = 0.0 if actions == ["fillWater"] and item.use_cost in (None, "", "-") else float(item.use_cost)

            char_id = kwargs['char_id']
            char = get_object_or_404(models.Character, id=char_id)
            if not request.user.is_authenticated or (char.owner != request.user.username and not request.user.is_superuser):
                return JsonResponse({'error': 'Brak dostępu do postaci.'}, status=403)
            eq_items = models.Eq.objects.filter(name=item.name, character=char.name, owner=char.owner)
            eq_id = request.GET.get('eq_id')
            if not eq_id:
                eq_id = eq_items.order_by('id').values_list('id', flat=True).first()
            eq_item = get_object_or_404(eq_items, id=eq_id)

            if not char.inFight:
                cost = 0.0

            if float(char.actionLeft) < cost and char.inFight:
                messages.error(request,f'Nie posiadasz wystarczająco akcji! Wymagane {cost} a dostępne {char.actionLeft}.')
                return redirect(f'/dunnorpg/items/ch{char_id}')

            if actions == ["fillWater"]:
                with transaction.atomic():
                    filled_name = fill_water(char, eq_item)
                    if char.inFight:
                        char.actionLeft -= cost
                        char.save(update_fields=["actionLeft"])
                messages.success(request, f'Napełniono wodą: {filled_name}.')
                return redirect(f'/dunnorpg/items/ch{char_id}')

            char, effect_messages = apply_item_use_effects(char, actions, cost, manageFoodAndWater, sync_alcohol_effects)
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

            if eq_item.use_amount and eq_item.use_amount >= 2:
                with transaction.atomic():
                    if eq_item.amount > 1:
                        unit_weight = eq_item.weight / eq_item.amount
                        models.Eq.objects.create(
                            owner=eq_item.owner,
                            character=eq_item.character,
                            name=eq_item.name,
                            type=eq_item.type,
                            weight=eq_item.weight - unit_weight,
                            durability=eq_item.durability,
                            amount=eq_item.amount - 1,
                            use_amount=eq_item.use_amount,
                            reloaded=eq_item.reloaded,
                            additional_description=eq_item.additional_description,
                        )
                        eq_item.amount = 1
                        eq_item.weight = unit_weight
                    eq_item.use_amount -= 1
                    eq_item.save()
            else:
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
        except ValueError as e:
            messages.error(request, str(e))
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

            chosen_class.mods = [mod.strip() for mod in chosen_class.mods.split(";") if mod.strip()]

            class_skills = models.Skills_Decs.objects.filter(
                restrictions__icontains=chosen_class.name
            ).order_by('name')

            context['class'] = chosen_class
            context['theme_list'] = [theme.strip() for theme in (chosen_class.positives or '').split(';') if theme.strip()]
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

class ImagesView(ListView):
    model = models.Images
    template_name = 'images.html'
    context_object_name = 'images'

    def get_template_names(self):
        if is_partial_request(self.request):
            return ['dunnorpg/images_results.html']
        return [self.template_name]

    def get_queryset(self):
        images = super().get_queryset().order_by('chapter', 'name')
        images = images.filter(chapter=get_current_chapter())
        search_value = self.request.GET.get('search-input')
        if search_value:
            images = images.filter(name__icontains=search_value)
        return images

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_value'] = self.request.GET.get('search-input', '')
        context['current_chapter'] = get_current_chapter()
        return context

def image_preview(request, id):
    image = models.Images.objects.filter(id=id).first()
    if not image:
        return render_404(request)

    if not image.visible and not request.user.is_superuser:
        return render_404(request)

    return render(request, 'image-preview.html', {'image': image})

@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_image_visible(request, id):
    image = get_object_or_404(models.Images, id=id)
    image.visible = not image.visible
    image.save(update_fields=['visible'])
    return JsonResponse({'visible': image.visible}, status=200)

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
                                    dur = clamp_item_durability(itemDesc, dur)

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
                                dur = clamp_item_durability(itemDesc, dur)
                                
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
            applied = add_active_effect(char.owner, char.name, effect.name, data['time'])
            messages.warning(request, f'Added {applied.name} to {char.name}.')
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

def set_current_chapter(request):
    if not request.user.is_superuser:
        return redirect('gm_panel')

    if request.method == 'POST':
        chapter = request.POST.get('current_chapter')
        if chapter in CHAPTER_CHOICES:
            settings = get_game_settings()
            settings.current_chapter = chapter
            settings.save(update_fields=['current_chapter'])
            messages.success(request, f"Current chapter changed to {chapter}.")
        else:
            messages.error(request, "Invalid chapter.")

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
        context['chapter_choices'] = CHAPTER_CHOICES
        context['current_chapter'] = get_current_chapter()
        #context['effect_form'] = AddEffectForm

        return context
    
    @transaction.atomic
    def form_valid(self, form):
        override = form.cleaned_data.get('override')
        equip_item = form.cleaned_data.get('equip_item')
        ignore_limits = form.cleaned_data.get('ignore_limits')
        form_data = form.save(commit=False)
        
        character = models.Character.objects.select_for_update().get(pk=form_data.character)
        form_data.owner = character.owner
        form_data.character = character.name
        
        item = models.Items.objects.get(pk=form_data.name)
        form_data.name = item.name
        form_data.type = item.type
        form_data.durability = clamp_item_durability(item, form_data.durability)
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
            if form_data.amount == 1 and is_character_accessory_item(item):
                target_position = "Akcesoria"
                equipped = get_equipped_item_for_place(character.name, target_position) is None
            elif form_data.amount == 1 and item_category in ["armor", "cloth", "armor_elegant"]:
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
                    durability=clamp_item_durability(item, form_data.durability),
                    hand=target_hand,
                    position=target_position,
                    reloaded=True,
                    additional_description=form_data.additional_description,
                )
                sync_item_granted_skills(character)
                messages.success(self.request, f"{item.name} equipped to {character.name}.")
                return super().form_valid(form)

            messages.warning(self.request, f"Nie udało się założyć {item.name} postaci {character.name}")
        
        if not ignore_limits and not can_add_item_to_eq_by_limits(character, item, form_data.amount):
            messages.error(self.request, f"{character.name} moze miec maksymalnie {MAX_BAG_ITEMS_IN_EQ} torby w ekwipunku.")
            return redirect('gm_panel')

        try:
            existing_item = get_object_or_404(
                models.Eq,
                name=item.name,
                character=character.name,
                durability=form_data.durability,
                additional_description=form_data.additional_description,
                use_amount=item.use_amount,
                book_trade_locked=False,
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
class InfoStory(TemplateView):
    template_name = 'info-story.html'
    book_path = Path(__file__).resolve().parent / 'json_data' / 'book.json'

    def get_template_names(self):
        if self.request.GET.get('partial') == '1':
            return ['dunnorpg/story_page.html']
        return super().get_template_names()

    @staticmethod
    def page_url(page):
        if page is None:
            return reverse('info_story')
        if page == 0:
            return reverse('info_story_contents')
        return reverse('info_story', kwargs={'page': page})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        with self.book_path.open(encoding='utf-8') as book_file:
            book = json.load(book_file)

        pages = book['pages']
        page_order = [None, *sorted(int(key.removeprefix('page')) for key in pages)]
        page = 0 if kwargs.get('contents') else kwargs.get('page') or None
        if page not in page_order:
            raise Http404

        index = page_order.index(page)
        if index > 0:
            context['previous_page_url'] = self.page_url(page_order[index - 1])
        if index + 1 < len(page_order):
            context['next_page_url'] = self.page_url(page_order[index + 1])

        context['is_cover'] = page is None
        context['page_number'] = page
        if page is None:
            context['page_title'] = book['title']
        else:
            entry = pages[f'page{page}']
            context['page_title'] = entry['title']
            content = []
            for line in entry['content']:
                link = None
                if page == 0:
                    match = re.search(r'\bstr\.\s*(\d+)\s*$', line, re.IGNORECASE)
                    if match:
                        target = int(match[1])
                        if target > 0 and target in page_order:
                            link = self.page_url(target)
                content.append({'text': line, 'url': link})
            context['page_content'] = content
        return context


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

    def get_template_names(self):
        if is_partial_request(self.request):
            return ['dunnorpg/info_effects_results.html']
        return [self.template_name]

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

def get_city_price_multiplier(available_amount, durability_percent):
    return 2.0 if int(available_amount) == 1 and durability_percent > 0.7 else 1.5

def get_city_item_shop(item):
    category = (item.category or "").strip().lower()
    item_type = (item.type or "").strip().lower()
    if item_type == BOOK_TYPE:
        return "Biblioteka"
    if category in {"trash", "lek"}:
        return "Kupiec"
    if category == "eliksir":
        return "Stoisko z eliksirami"
    if category in CITY_TAVERN_BUY_CATEGORIES or category == "tawerna":
        return "Karczma"
    if category.startswith("trophy_"):
        return "Myśliwy"
    if category == "animal" or category.startswith("animal_") or item_type in {"animal", "mount armor"}:
        return "Handlarz zwierząt"
    if category in {"weapon_music", "item_music"}:
        return "Kramarz muzyczny"
    if is_city_range_shop_item(category):
        return "Łuczarz"
    if is_city_gunpowder_shop_item(category):
        return "Rusznikarz"
    if category == "armor":
        return "Płatnerz"
    if category in {"cloth", "bag"}:
        return "Krawiec"
    if category == "armor_elegant":
        return "Jubiler"
    if item_type in {"amulet", "other"} or item_type in CHARACTER_ACCESSORY_TYPES:
        return "Kupiec"
    if item_type in {"helmet", "torso", "gloves", "boots"}:
        return "Płatnerz"
    return "Kowal"


def get_city_unit_price(item, available_amount, durability_percent, *, allfree=False, discount=""):
    if allfree:
        return 0.0
    base_price = float(f"{item.price * get_city_price_multiplier(available_amount, durability_percent):.1f}")
    unit_price = Decimal(f"{base_price * durability_percent:.1f}")
    discounts = parse_city_discounts(discount)
    discount_percent = discounts.get(get_city_item_shop(item).casefold(), discounts.get("all", 0))
    return float((unit_price * (100 - discount_percent) / 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))

def get_city_total_price(item, available_amount, durability_percent, amount, *, allfree=False, discount=""):
    return float(f"{get_city_unit_price(item, available_amount, durability_percent, allfree=allfree, discount=discount) * int(amount):.1f}")

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

def get_city_armor_weight_label(item):
    labels = {
        "light": "Lekkie",
        "light+": "Lekkie+",
        "medium": "Srednie",
        "medium+": "Srednie+",
        "heavy": "Ciezkie",
    }
    explicit_weight = (item.armor_weight or "").strip().lower()
    if explicit_weight in labels:
        return labels[explicit_weight]

    order = get_city_armor_weight_order(item)
    return {
        ARMOR_WEIGHT_ORDER["light"]: "Lekkie",
        ARMOR_WEIGHT_ORDER["medium"]: "Srednie",
        ARMOR_WEIGHT_ORDER["heavy"]: "Ciezkie",
    }.get(order, "Bron")

def is_city_range_shop_item(item_category):
    return "range" in item_category

def is_city_gunpowder_shop_item(item_category):
    return "gun" in item_category or "gunpowder" in item_category

def get_city_item_stat(item):
    if (item.type or "").strip().lower() == "shield":
        return f"Blok: {item.block}"
    if (item.type or "").strip().lower() == "amunicja":
        return f"{item.dmgModifier:g}x"
    return f"{item.dmgDice}, {item.AP}% AP"

def should_show_city_capacity(item):
    item_category = (item.category or "").strip().lower()
    item_type = (item.type or "").strip().lower()
    item_name = (item.name or "").lower()
    return item_category == "bag" or (
        item_category == "cloth"
        and item_type == "akcesoria"
        and "pas" in item_name
    )

def get_city_animal_groups(items, categories):
    labels = {
        "animal_saddle": "Siodło/Juki",
        "animal_horseshoes": "Podkowy",
        "animal_armor": "Pancerz",
        "animal": "Zwierzę",
        "other": "Pozostałe",
    }
    groups = {key: [] for key in labels}
    for item in items:
        category = categories.get(item, "")
        if category not in groups:
            item_type = (item.item_type or "").strip().lower()
            category = {"animal": "animal", "mount armor": "animal_armor"}.get(item_type, "other")
        groups[category].append(item)
    return [(label, groups[key]) for key, label in labels.items()]

def get_city_armor_groups(items, categories):
    labels = {
        "helmet": "Hełm",
        "torso": "Napierśnik",
        "gloves": "Rękawice",
        "boots": "Nogi",
        "akcesoria": "Akcesoria",
        "amulet": "Amulet",
        "bag": "Torby",
        "other": "Pozostałe",
    }
    groups = {key: [] for key in labels}
    for item in items:
        item_type = (item.item_type or "").strip().lower()
        if categories.get(item) == "bag":
            item_type = "bag"
        groups[item_type if item_type in groups else "other"].append(item)
    return [(label, groups[key]) for key, label in labels.items()]

def get_city_weapon_groups(items):
    singlehand = []
    twohand = []
    ammunition = []
    accessories = []
    other = []
    for item in items:
        if item.is_city_accessory:
            accessories.append(item)
        elif (item.item_type or "").strip().lower() == "amunicja":
            ammunition.append(item)
        elif (item.item_type or "").strip().lower() == "other":
            other.append(item)
        elif item.dual_handed:
            twohand.append(item)
        else:
            singlehand.append(item)
    return [
        ("Jednoręczne", singlehand),
        ("Dwuręczne", twohand),
        ("Amunicja", ammunition),
        ("Akcesoria", accessories),
        ("Inne", other),
    ]

def get_city_nested_weapon_groups(items):
    groups = []
    for label, group_items in get_city_weapon_groups(items):
        types = {}
        for item in group_items:
            item_type = (item.item_type or "").strip().lower()
            if item_type == "amunicja" and item.ammo_type in {"bolt", "arrow"}:
                item_type = item.ammo_type
            types.setdefault(item_type, []).append(item)
        groups.append((label, sorted(types.items())))
    return groups

CITY_TAVERN_BUY_CATEGORIES = {"alkohol", "jedzenie"}

class CityShopItem(str):
    def __new__(cls, item, durability_percent, sale_index):
        name = item.name
        obj = str.__new__(cls, name)
        obj.durability_percent = durability_percent
        obj.sale_index = sale_index
        obj.item_id = item.id
        obj.item_type = item.type
        obj.is_city_accessory = (item.type or "").strip().lower() in CHARACTER_ACCESSORY_TYPES
        obj.is_city_merchant_equipment = obj.is_city_accessory or (item.type or "").strip().lower() == "amulet"
        obj.ammo_type = (item.ammo_type or "").strip().lower()
        obj.item_category = (item.category or "").strip().lower()
        obj.is_city_equipment = (item.type or "").strip().lower() in {
            "helmet", "torso", "gloves", "boots", "akcesoria", "amulet",
        }
        obj.is_ammunition = (item.type or "").strip().lower() == "amunicja"
        obj.item_ap = f"{item.AP:+d}%AP"
        obj.dual_handed = item.dualHanded
        obj.rarity = item.rarity
        obj.extra_capacity = item.extra_capacity
        obj.show_city_capacity = should_show_city_capacity(item)
        obj.armor_weight_label = get_city_armor_weight_label(item)
        obj.armor_weight_rank = get_city_armor_weight_order(item)
        obj.has_class_armor_limit = (item.type or "").strip().lower() in ARMOR_WEIGHT_LIMITED_POSITIONS
        obj.item_stat = get_city_item_stat(item)
        obj.item_range = item_effective_range(item) if is_weapon_item(item) else None

        skill = item.skill or ""
        obj.use_info = item.use_info or ""
        if obj.item_category in CITY_TAVERN_BUY_CATEGORIES and item.use_amount is not None:
            obj.use_info = f"{obj.use_info} | {item.use_amount}" if obj.use_info else str(item.use_amount)
        if (item.category or "").strip().lower() == "tawerna" and skill:
            obj.use_info = f"{obj.use_info} | {skill}" if obj.use_info else skill
        if obj.item_category in CITY_TAVERN_BUY_CATEGORIES and obj.use_info:
            skill = f"{obj.use_info.rstrip('. ')}. {skill}" if skill else obj.use_info
        obj.skill_text = skill
        obj.skill_preview_limit = 100
        obj.visible_skill = skill[:100] + "..." if len(skill) > 100 else skill
        return obj

    def __hash__(self):
        return hash((str(self), self.durability_percent, self.sale_index))

    def __eq__(self, other):
        if isinstance(other, CityShopItem):
            return self.sale_index == other.sale_index
        return str.__eq__(self, other)

def set_city_book_reading_warnings(books, characters):
    if not books or not characters:
        return

    book_targets = [
        (book, (book.book_category or '').strip().casefold(), book_skill_targets(book.book_skills))
        for book in books
    ]
    class_names = {character.chosen_class for character in characters}
    magical_class_names = set()
    if any(category == GRIMOIRE_CATEGORY for _, category, _ in book_targets):
        magical_class_names = set(magical_classes(class_names).values_list('name', flat=True))

    advanced_skill_names = {
        key for _, category, targets in book_targets if category == ADVANCED_BOOK_CATEGORY for key in targets
    }
    skill_ids = {}
    if advanced_skill_names:
        for skill_id, name in models.Skills_Decs.objects.order_by('pk').values_list('pk', 'name'):
            if name.casefold() in advanced_skill_names:
                skill_ids.setdefault(name.casefold(), skill_id)
    available_by_class = {
        class_name: set(skills_available_in_editor(class_name).filter(
            pk__in=skill_ids.values(),
        ).values_list('pk', flat=True))
        for class_name in class_names
    }

    higher_skill_names = {key for _, _, targets in book_targets for key, (_, level) in targets.items() if level > 1}
    levels_by_character = {(character.owner, character.name): {} for character in characters}
    if higher_skill_names:
        skills = permanent_skills().filter(
            owner__in={character.owner for character in characters},
            character__in={character.name for character in characters},
        ).order_by('pk').values_list('owner', 'character', 'skill', 'level')
        for owner, character_name, skill_name, level in skills:
            levels = levels_by_character.get((owner, character_name))
            if levels is not None and skill_name.casefold() in higher_skill_names:
                levels.setdefault(skill_name.casefold(), level or 0)

    for book, category, targets in book_targets:
        required_ids = {skill_ids[key] for key in targets if key in skill_ids}
        warnings = {}
        for character in characters:
            class_name = character.chosen_class
            if category == GRIMOIRE_CATEGORY and class_name not in magical_class_names:
                warnings[character.pk] = 'Grymuar wymaga klasy z kategorii Magiczne'
                continue
            if category == ADVANCED_BOOK_CATEGORY and not required_ids.issubset(available_by_class[class_name]):
                warnings[character.pk] = 'Klasa postaci nie ma dostępu do umiejętności z tej książki'
                continue
            levels = levels_by_character[(character.owner, character.name)]
            for key, (name, level) in targets.items():
                warning = book_previous_level_error(name, level, levels.get(key, 0))
                if warning:
                    warnings[character.pk] = warning
                    break
        book.reading_warnings = json.dumps(warnings, ensure_ascii=False) if warnings else ''


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
        context['city'] = city
        if self.request.user.is_superuser:
            context['cities'] = models.Cities.objects.order_by(Lower("city_name"))
        if not is_empty:
            discounts = parse_city_discounts(city.discount)
            context['city_discount'] = discounts.get('all', 0)
            context['shop_labels'] = {}
            for shop in CITY_SHOPS:
                percent = discounts.get(shop.casefold())
                show_discount = percent is not None and (percent > 0 or context['city_discount'] > 0)
                context['shop_labels'][shop] = f'{shop} [-{percent}%]' if show_discount else shop
            items = sorted(city.items.split(';'))
            parsed_items = [parse_city_item_entry(entry) for entry in items]
            item_names = {name for name, _, _ in parsed_items if name}
            item_descriptions = {}
            for item_description in models.Items.objects.filter(name__in=item_names):
                item_descriptions.setdefault(item_description.name, item_description)
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
            ranged_weaponry = []
            gunpowder_weaponry = []
            musical_weaponry = []
            potions = []
            books = []
            trophies = []
            other = []
            medicines = []
            animals = []
            bags = []
            tavern = []
            amounts = {}
            durabilities = {}
            durability_percents = {}
            city_prices = {}
            city_armors = {}
            armor_weight_orders = {}
            city_categories = {}
            tavern_buy_items = []
            armor_shop_categories = ["armor", "cloth", "armor_elegant"]
            
            found_item_ids = []
            for sale_index, (item_name, durability, amount) in enumerate(parsed_items):
                item = item_descriptions.get(item_name)

                if item != None:
                    item_category = (item.category or "").strip().lower()
                    if int(amount) == 0 and item_category != "tawerna":
                        continue

                    if durability is None:
                        durability = 100
                    durability = min(durability, 100)

                    item_durability = get_durability_from_percent(durability, item.maxDurability)
                    item_durability = clamp_item_durability(item, item_durability)

                    if not item.found:
                        found_item_ids.append(item.id)

                    shop_item = CityShopItem(item, durability, sale_index)

                    amounts[shop_item] = amount
                    durabilities[shop_item] = item_durability
                    durability_percent = durability / 100
                    durability_percents[shop_item] = f"{durability:.0f}%"
                    shop_item.unit_price = f"{get_city_unit_price(item, amount, durability_percent, allfree=city.allfree, discount=city.discount):.1f}"
                    shop_item.available_amount = amount
                    city_prices[shop_item] = shop_item.unit_price
                    city_armors[shop_item] = math.ceil(item.armor * durability_percent) if item.armor else item.armor
                    armor_weight_orders[shop_item] = get_city_armor_weight_order(item)
                    city_categories[shop_item] = item_category
                    if (item.type or '').strip().casefold() == BOOK_TYPE:
                        shop_item.book_category = item.category
                        shop_item.book_skills = parse_item_granted_skills(item.grantedSkills)
                        books.append(shop_item)
                    elif item_category == "trash":
                        other.append(shop_item)
                    elif item_category == "lek":
                        medicines.append(shop_item)
                    elif item_category == "eliksir":
                        potions.append(shop_item)
                    elif item_category in CITY_TAVERN_BUY_CATEGORIES:
                        tavern_buy_items.append(shop_item)
                    elif item_category == "tawerna":
                        tavern.append(shop_item)
                    elif item_category.startswith("trophy_"):
                        trophies.append(shop_item)
                    elif item_category == "animal" or item_category.startswith("animal_") or (item.type or "").strip().lower() in {"animal", "mount armor"}:
                        animals.append(shop_item)
                    elif item_category in {"weapon_music", "item_music"}:
                        musical_weaponry.append(shop_item)
                    elif is_city_range_shop_item(item_category):
                        ranged_weaponry.append(shop_item)
                    elif is_city_gunpowder_shop_item(item_category):
                        gunpowder_weaponry.append(shop_item)
                    elif item_category in armor_shop_categories:
                        all_armor.append(shop_item)
                    elif item_category == "bag":
                        bags.append(shop_item)
                    elif item.type == 'Amulet':
                        amulets.append(shop_item)
                    elif item.type == 'Other' or shop_item.is_city_accessory:
                        other.append(shop_item)
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

            if found_item_ids:
                models.Items.objects.filter(id__in=found_item_ids).update(found=True)
            

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
            tailor_items = cloth + bags
            armor_elegant = [item_name for item_name in all_armor if city_categories.get(item_name) == "armor_elegant"]

            x5packets = []
            x10packets = ["Strzała","Pocisk do broni prochowej"]

            context['weaponry_singlehand'] = weaponry_singlehand
            context['weaponry_twohand'] = weaponry_twohand
            context['smith_weapon_type_groups'] = get_city_nested_weapon_groups(weaponry_singlehand + weaponry_twohand)
            context['ranged_weapon_type_groups'] = get_city_nested_weapon_groups(ranged_weaponry)
            context['ranged_weaponry'] = ranged_weaponry
            context['gunpowder_weaponry'] = gunpowder_weaponry
            context['ranged_weapon_groups'] = get_city_weapon_groups(ranged_weaponry)
            context['gunpowder_weapon_groups'] = get_city_weapon_groups(gunpowder_weaponry)
            context['musical_weaponry'] = musical_weaponry
            context['armor'] = armor
            context['cloth'] = cloth
            context['tailor_items'] = tailor_items
            context['armor_groups'] = get_city_armor_groups(armor, city_categories)
            context['tailor_groups'] = get_city_armor_groups(tailor_items, city_categories)
            context['armor_elegant'] = armor_elegant
            context['amulets'] = amulets
            context['potions'] = potions
            context['books'] = books
            context['trophies'] = trophies
            context['animals'] = animals
            context['animal_groups'] = get_city_animal_groups(animals, city_categories)
            context['tavern'] = tavern
            context['tavern_groups'] = [
                ("Pokoje", [item for item in tavern if item.item_type == "Pokój"]),
                ("Posiłki", [item for item in tavern if item.item_type != "Pokój"]),
            ]
            context['tavern_buy_items'] = tavern_buy_items
            context['other'] = other + medicines
            context['merchant_groups'] = [
                ("Akcesoria", [item for item in other if item.is_city_accessory]),
                ("Amulety", [item for item in other if (item.item_type or "").strip().lower() == "amulet"]),
                ("Medykamenty", medicines),
                ("Pozostałe", [item for item in other if not item.is_city_merchant_equipment]),
            ]
            context['x5packets'] = x5packets
            context['x10packets'] = x10packets
            context['amounts'] = amounts
            context['durabilities'] = durabilities
            context['durability_percents'] = durability_percents
            context['city_prices'] = city_prices
            context['city_armors'] = city_armors
            context['city_categories'] = city_categories
            characters_query = models.Character.objects.filter(hidden=False)
            if not self.request.user.is_superuser:
                characters_query = characters_query.filter(owner=self.request.user)
            characters = list(characters_query)
            context['characters'] = characters
            set_city_book_reading_warnings(books, characters)
            context['injured_characters'] = []
            for character in characters:
                if character.fullHP is not None and character.HP < character.fullHP:
                    character.healing_base_cost = (character.fullHP - character.HP) * Decimal('0.5')
                    context['injured_characters'].append(character)

            character_names = [character.name for character in characters]
            equipped_items = list(models.CharItems.objects.filter(character__in=character_names))
            equipped_descriptions = {
                item.name: item for item in models.Items.objects.filter(
                    name__in={equipped.name for equipped in equipped_items}
                )
            }
            charisma_mods = {name: 0 for name in character_names}
            for mod in models.Mods.objects.filter(character__in=character_names, field="CHAR"):
                charisma_mods[mod.character] = charisma_mods.get(mod.character, 0) + mod.value
            for equipped_item in equipped_items:
                description = equipped_descriptions.get(equipped_item.name)
                for stat in (description.skillStats or "").split(";") if description else []:
                    if stat[:-2].lower() != "char" or len(stat) < 2:
                        continue
                    try:
                        charisma_mods[equipped_item.character] += int(stat[-2:])
                    except ValueError:
                        pass
            class_armor_ranks = {
                character_class.name: ARMOR_WEIGHT_ORDER.get(
                    (character_class.armor_weight or "").strip().lower(), ARMOR_WEIGHT_ORDER["all"]
                )
                for character_class in models.Classes.objects.filter(
                    name__in={character.chosen_class for character in characters}
                )
            }
            for character in characters:
                character.city_armor_weight_rank = class_armor_ranks.get(character.chosen_class, ARMOR_WEIGHT_ORDER["all"])
                value = charisma_mods.get(character.name, 0) + effect_stat_modifier(character, "CHAR")
                character.city_char_mod = f"+{value}" if value >= 0 else str(value)

            healing_charisma = characters[0].CHAR + int(characters[0].city_char_mod) if characters else 0
            for character in context['injured_characters']:
                character.healing_cost = get_city_healing_price(
                    character.healing_base_cost, 0 if self.request.user.is_superuser else healing_charisma,
                )

            if city.repair:
                items_by_character = {name: [] for name in character_names}
                inventory_items = list(models.Eq.objects.filter(character__in=character_names))
                repair_descriptions = dict(equipped_descriptions)
                repair_descriptions.update({item.name: item for item in models.Items.objects.filter(
                    name__in={item.name for item in inventory_items},
                )})
                characters_by_name = {character.name: character for character in characters}
                for repair_item in equipped_items + inventory_items:
                    character = characters_by_name[repair_item.character]
                    description = repair_descriptions.get(repair_item.name)
                    if description is None or repair_item.owner != character.owner:
                        continue
                    base_cost = get_city_repair_base_price(description, repair_item)
                    if base_cost is None:
                        continue
                    repair_item.rarity = description.rarity
                    repair_item.repair_source = 'eq' if isinstance(repair_item, models.Eq) else 'char'
                    repair_item.repair_amount = repair_item.amount if repair_item.repair_source == 'eq' else 1
                    repair_item.durability_percent = max(0, repair_item.durability) / description.maxDurability * 100
                    repair_item.repair_cost = get_city_healing_price(
                        base_cost, character.CHAR + int(character.city_char_mod),
                    )
                    items_by_character[repair_item.character].append(repair_item)
                for character in characters:
                    character.repair_items = items_by_character.get(character.name, [])


        return context       

@require_POST
def change_visiting_city(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Brak uprawnien do zmiany miasta."}, status=403)

    try:
        data = json.loads(request.body or "{}")
        city_id = int(data.get("city_id"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Nieprawidlowe miasto."}, status=400)

    with transaction.atomic():
        city = get_object_or_404(models.Cities.objects.select_for_update(), id=city_id)
        models.Cities.objects.exclude(id=city.id).update(visiting=False)
        if not city.visiting:
            city.visiting = True
            city.save(update_fields=["visiting"])

    return JsonResponse({"city_id": city.id, "city_name": city.city_name})

class BuyItem(APIView):
    def purchase_response(self, request, message, success=False, **data):
        if request.method == "POST":
            return JsonResponse({"success": success, "message": message, **data}, status=200 if success else 400)
        (messages.success if success else messages.error)(request, message)
        return redirect('/dunnorpg/city')

    def post(self, request, **kwargs):
        return self.get(request, **kwargs)

    @transaction.atomic
    def get(self,request,**kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "message": "Zaloguj się, aby kupować."}, status=403)
        item = get_object_or_404(models.Items, id=kwargs['item_id'])
        characters = models.Character.objects.select_for_update().filter(hidden=False)
        if not request.user.is_superuser:
            characters = characters.filter(owner=request.user.username)
        character = get_object_or_404(characters, id=kwargs['character_id'])
        city = get_object_or_404(models.Cities.objects.select_for_update(), visiting=True)
        item_amount = int(kwargs['amount'])
        if item_amount < 1:
            return self.purchase_response(request, "Podaj dodatnią liczbę sztuk.")
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
            ct_item_durability_percent = min(ct_item_durability_percent, 100)
            if ct_item_name == item.name and (requested_durability is None or requested_durability == ct_item_durability_percent):
                item_durability_percent = ct_item_durability_percent
                item_durability = get_durability_from_percent(item_durability_percent, item.maxDurability)
                item_durability = clamp_item_durability(item, item_durability)
                available_amount = amount
                break

        if available_amount <= 0:
            return self.purchase_response(request, 'Za późno, wszystkie już wyszły!')

        if item_amount > available_amount:
            item_amount = available_amount

        if not can_add_item_to_eq_by_limits(character, item, item_amount):
            return self.purchase_response(request, f"{character.name} moze miec maksymalnie {MAX_BAG_ITEMS_IN_EQ} torby w ekwipunku.")

        max_weight = get_character_max_weight(character)
        current_weight = get_character_current_weight(character)

        if current_weight+item.weight*item_amount <= max_weight:
            durability_percent = item_durability_percent / 100
            price = get_city_total_price(item, available_amount, durability_percent, item_amount, allfree=city.allfree, discount=city.discount)
            charisma = character.CHAR + effect_stat_modifier(character, "CHAR")

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
            price = float(f"{price - char_bonus:.1f}")

            if character.coins >= price:

                city_items = city.items.split(";")
                for ct_item in city_items:
                    ct_item_name, ct_item_durability, amount = parse_city_item_entry(ct_item)
                    ct_item_durability_percent = 100 if ct_item_durability is None else ct_item_durability
                    ct_item_durability_percent = min(ct_item_durability_percent, 100)
                    if ct_item_name == item.name and (requested_durability is None or requested_durability == ct_item_durability_percent):
                        index = city_items.index(ct_item)
                        if ct_item_durability is None:
                            ct_item_durability = 100

                        if int(amount)<=0:
                            return self.purchase_response(request, f'Za późno, wszystkie już wyszły!')

                        new_amount = int(amount)-int(item_amount)
                        if new_amount<0:
                            item_amount+=new_amount
                            new_amount = int(amount)-int(item_amount) #should be 0
                        ct_new_item = format_city_item_entry(ct_item_name, ct_item_durability, new_amount)
                        city_items[index] = ct_new_item
                        item_durability_percent = min(ct_item_durability, 100)
                        item_durability = get_durability_from_percent(item_durability_percent, item.maxDurability)
                        item_durability = clamp_item_durability(item, item_durability)

                city.items = ';'.join(city_items)
                city.save()

                character.coins -= price
                character.save()
                
                #if item.name in ["Strzała","Pocisk do broni prochowej"]:
                #    item_amount = item_amount*10
                try:
                    item_durability = clamp_item_durability(item, item_durability)
                    existing_item = get_object_or_404(
                        models.Eq, name=item.name, character=character.name, durability=item_durability,
                        use_amount=item.use_amount, book_trade_locked=False,
                    )
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

                return self.purchase_response(
                    request, f'[{character.name}] Zakupiono {item_amount}x {item.name} za {price} monet.',
                    success=True, item_id=item.id, durability=item_durability_percent,
                    available_amount=new_amount,
                    unit_price=get_city_unit_price(item, new_amount, item_durability_percent / 100, allfree=city.allfree, discount=city.discount),
                    character_id=character.id, coins=character.coins,
                )
            else:
                return self.purchase_response(request, f'Za mało monet. {character.name} ma ich {character.coins}, a potrzeba {price}.')
        else:
            return self.purchase_response(request, f'Za mało miejsca! Nosisz już {current_weight}/{max_weight}kg.')

        return redirect('/dunnorpg/city')

class OrderTavernItem(APIView):
    def get(self, request, **kwargs):
        item = get_object_or_404(models.Items, id=kwargs['item_id'], category__iexact="Tawerna")
        character = get_object_or_404(models.Character, id=kwargs['character_id'])
        city = get_object_or_404(models.Cities, visiting=True)
        item_amount = max(1, int(kwargs.get('amount', 1)))

        item_durability_percent = None
        available_amount = 1
        for ct_item in city.items.split(";"):
            if not ct_item.strip():
                continue
            ct_item_name, ct_item_durability, amount = parse_city_item_entry(ct_item)
            if ct_item_name == item.name:
                item_durability_percent = 100 if ct_item_durability is None else ct_item_durability
                available_amount = amount
                break

        if item_durability_percent is None:
            messages.error(request, f'{item.name} nie jest dostępne w tej karczmie.')
            return redirect('/dunnorpg/city')

        if available_amount > 0:
            item_amount = min(item_amount, available_amount)

        price = get_city_total_price(item, available_amount, item_durability_percent / 100, item_amount, allfree=city.allfree, discount=city.discount)
        if character.coins < price:
            messages.error(request, f'Za mało monet. {character.name} ma ich {character.coins}, a potrzeba {price}.')
            return redirect('/dunnorpg/city')

        actions = [part.strip() for part in (item.on_use or "").split(";") if part.strip()]
        if not actions:
            messages.error(request, f'{item.name} nie ma ustawionego on_use.')
            return redirect('/dunnorpg/city')

        character.coins -= price
        effect_messages = []
        for _ in range(item_amount):
            character, current_effect_messages = apply_item_use_effects(
                character,
                actions,
                0.0,
                manageFoodAndWater,
                sync_alcohol_effects,
                add_consumed_container=False,
            )
            effect_messages += current_effect_messages
        character.save()

        for effect_message in effect_messages:
            getattr(messages, effect_message.level)(request, effect_message.text)
        messages.success(request, f'[{character.name}] Zamówiono {item_amount}x {item.name} za {price} monet.')
        return redirect('/dunnorpg/city')

def get_city_healing_price(base_cost, charisma):
    discount = (base_cost * Decimal(charisma) * Decimal('0.02')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    return max(Decimal('0'), base_cost - discount)


@require_POST
@transaction.atomic
def heal_character(request, char_id):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Zaloguj się, aby leczyć postacie.'}, status=403)
    city = get_object_or_404(models.Cities.objects.select_for_update(), visiting=True)
    if not city.healer:
        return JsonResponse({'message': 'Uzdrowiciel nie jest dostępny w tym mieście.'}, status=403)
    characters = models.Character.objects.select_for_update().filter(hidden=False)
    if not request.user.is_superuser:
        characters = characters.filter(owner=request.user.username)
    character = get_object_or_404(characters, id=char_id)
    charisma = 0
    if not request.user.is_superuser:
        try:
            selected_id = int(request.POST.get('charisma_character_id', ''))
        except (TypeError, ValueError):
            return JsonResponse({'message': 'Wybierz postać, której charyzma wpływa na cenę leczenia.'}, status=400)
        selected = get_object_or_404(characters, id=selected_id)
        charisma = get_city_character_charisma(selected)
    if character.fullHP is None or character.HP >= character.fullHP:
        return JsonResponse({'message': 'Ta postać nie wymaga leczenia.'}, status=400)
    healed = character.fullHP - character.HP
    cost = get_city_healing_price(healed * Decimal('0.5'), charisma)
    coins = Decimal(str(character.coins))
    if coins < cost:
        return JsonResponse({'message': f'Za mało monet. Leczenie kosztuje {cost:g} monet. Brakuje {cost - coins:g} monet.'}, status=400)
    character.HP = character.fullHP
    character.coins = float(coins - cost)
    character.save(update_fields=['HP', 'coins'])
    return JsonResponse({
        'message': f'Wyleczono {character.name} do pełnego PŻ ({character.fullHP}). Koszt: {cost:g} monet.',
        'character_id': character.id, 'hp': character.HP, 'coins': character.coins,
        'cost': float(cost), 'healed': healed,
    })

class SignUp(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"
    
def view_404(request, exception):
    return render_404(request)
