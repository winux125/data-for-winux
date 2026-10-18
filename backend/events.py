"""Merge observed episodes without adding another binary classifier."""
import re

SPECIFIC_ACTIONS = ('left_workplace', 'phone_in_hands', 'personal_items', 'cash_unattended', 'bag_opened')
LABELS = {
    'left_workplace': 'Уход с рабочего места', 'phone_in_hands': 'Использование телефона',
    'personal_items': 'Личные предметы в рабочей зоне', 'cash_unattended': 'Наличные без присмотра',
    'bag_opened': 'Вскрытие сумки', 'cash_receipt': 'Приём наличных', 'cash_issue': 'Выдача наличных',
    'cash_counting': 'Пересчёт наличных', 'cash_sorting': 'Сортировка наличных',
    'cash_packaging': 'Упаковка наличных',
}


def confirmed(event):
    return {f['predicate'] for f in event['facts'] if f['status'] == 'confirmed'}


def signature(event):
    predicates = confirmed(event)
    role = event.get('actor_role', 'unknown')
    specific = tuple(p for p in SPECIFIC_ACTIONS if p in predicates)
    if specific:
        return role, specific[0]
    if predicates == {'other_observed_action'}:
        return role, 'other', re.sub(r'\W+', ' ', event['description'].lower()).strip()
    return role, tuple(sorted(predicates))


def select_observations(candidates, peak=None):
    """Preserve v3 review semantics; merge repeats before normative calls.

    No unvalidated risk_level gate and no hard top-three cut.
    """
    ordered = sorted(candidates, key=lambda e: (
        not confirmed(e).intersection(SPECIFIC_ACTIONS),
        abs(e['time']-peak) if peak is not None else e['time']))
    chosen = []
    for event in ordered:
        if not any(f['status'] != 'unknown' for f in event['facts']):
            continue
        duplicate = next((e for e in chosen if abs(e['time']-event['time']) < 6
                          and signature(e) == signature(event)), None)
        if duplicate is None:
            chosen.append(dict(event, facts=list(event['facts']), frames=list(event['frames'])))
            continue
        seen = {(f['predicate'],f['status'],f['statement']) for f in duplicate['facts']}
        duplicate['facts'].extend(f for f in event['facts']
                                 if (f['predicate'],f['status'],f['statement']) not in seen)
        support = duplicate.get('support_frames',duplicate['frames']) + event.get('support_frames',event['frames'])
        duplicate['support_frames'] = list({f.timestamp:f for f in support}.values())
    return chosen


def action_type(event):
    predicates = confirmed(event)
    for predicate, label in LABELS.items():
        if predicate in predicates:
            return 'Наблюдаемое действие: ' + label
    return 'Наблюдение для проверки'
