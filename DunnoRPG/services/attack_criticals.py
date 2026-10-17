import json
import random
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / 'json_data'


def resolve_critical(roll, damage_type, piercing_choice='ignore_block'):
    rules = json.loads((DATA_DIR / 'attack_criticals.json').read_text(encoding='utf-8'))
    result = {'kind': None, 'ap_bonus': 0, 'ap_multiplier': 1, 'ap_cap': None}
    if roll == 20:
        damage_type = (damage_type or '').strip().casefold()
        effect = rules['hits'].get(damage_type)
        result.update(kind='hit', name=effect['name'] if effect else 'Trafienie krytyczne',
                      description=effect['description'] if effect else 'Brak zdefiniowanego skutku dla tego typu obrażeń.')
        if damage_type == 'sieczne':
            rolls = [random.randint(1, 20), random.randint(1, 20)]
            result['ap_bonus'] = max(20, sum(rolls))
            result['description'] += f" Wylosowano {rolls[0]} + {rolls[1]}: +{result['ap_bonus']}% AP."
        elif damage_type == 'kłute':
            result['ap_bonus'] = 25 if piercing_choice == 'ap' else 0
            result['description'] = '+25% AP.' if piercing_choice == 'ap' else 'Atak ignoruje blok tarczą.'
        elif damage_type == 'dystansowe':
            result['ap_bonus'] = 20
        elif damage_type == 'prochowe':
            result.update(ap_multiplier=2, ap_cap=100)
    elif roll == 1:
        index = random.randint(1, 6)
        result.update(rules['failures'][index - 1])
        result.update(kind='failure', failure_roll=index)
        if index == 4:
            result['body_part'] = random.choice(['rękę', 'nogę'])
            result['self_damage'] = random.randint(1, 6)
            result['description'] = f"Otrzymujesz {result['self_damage']} obrażeń w {result['body_part']} (K6)."
        elif index == 6:
            definitions = json.loads((DATA_DIR / 'definitions.json').read_text(encoding='utf-8'))
            result['effect_name'] = 'Powalenie'
            result['effect_description'] = definitions['Powalenie']
    return result
