"""Applying one norm to an ObservationBundle; the decision is always computed by code.

Two ways to obtain the norm's conditions and exceptions:
  card     a draft or reviewed rule card with an explicit condition_map (predicate, polarity);
           an item without a mapping stays unknown — no mapping is ever guessed;
  reading  call A of the generator on a norm without a card: requirement, conditions and
           exceptions with exact quotes, linked to fact IDs; `validate_reading` checks it and
           the states are then derived from the original fact statuses, not from the model.
Unknown is never false. A refuted fact is an observed absence and keeps its polarity.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .contracts import FACETS, ROLES, ConditionMapping, RequirementItem, combine_states

MODALITIES = ('prohibition', 'obligation', 'permission')
MODALITY_BY_KIND = {'commission': 'prohibition', 'state': 'prohibition', 'omission': 'obligation'}
# Predicates about the presence of another person are not scoped to the acting employee.
OTHER_PARTY_SUFFIX = '_present'
EXCEPTION_MARKERS = ('за исключением', 'не распространяется', 'кроме', 'не применяется', 'допускается',
                     'если иное', 'в случае если', 'не требуется')
PROHIBITION_CUES = ('запрещ', 'не допуска', 'не разреша', 'не вправе', 'не долж', 'не может', 'не могут', 'не следует')
MIN_QUOTE_CHARS = 12


@dataclass(frozen=True)
class Scope:
    subject_actor_id: str | None
    operation_id: str | None
    object: str | None = None
    window: tuple | None = None


# Card path -------------------------------------------------------------------

def card_scopes(card, bundle):
    """Scopes (acting employee, operation) defined by the facts of the card's trigger predicates."""
    triggers = [f for f in bundle.facts if f.predicate in card.trigger_predicates]
    decided = [f for f in triggers if f.status == 'confirmed'] or triggers
    scopes = []
    for fact in decided:
        window = (fact.t_start, fact.t_end) if fact.t_start is not None and fact.t_end is not None else None
        scope = Scope(fact.actor_id, fact.operation_id, fact.object, window)
        if scope not in scopes:
            scopes.append(scope)
    return scopes or [Scope(None, None)]


def _in_scope(fact, scope):
    if scope.operation_id is not None and fact.operation_id != scope.operation_id:
        return False
    if scope.object is not None and fact.object is not None and fact.object != scope.object:
        return False
    if scope.window is not None and (fact.t_start is None or fact.t_end is None or
                                    fact.t_start > scope.window[1] or fact.t_end < scope.window[0]):
        return False
    if fact.predicate.endswith(OTHER_PARTY_SUFFIX):
        return True
    return scope.subject_actor_id is None or fact.actor_id == scope.subject_actor_id


def _predicate_state(bundle, predicate, polarity, scope):
    facts = [f for f in bundle.facts if f.predicate == predicate and _in_scope(f, scope)]
    combined = combine_states(facts)
    ids = tuple(f.fact_id for f in facts if f.status != 'unknown')
    if combined.status in ('conflict', 'scope_required'):
        return ConditionMapping('', 'unknown', (), f'{combined.status}:{predicate}')
    if combined.status == 'unknown':
        return ConditionMapping('', 'unknown', (), f'no_decided_fact:{predicate}')
    holds = combined.status == 'confirmed'
    value = holds if polarity == 'positive' else not holds
    return ConditionMapping('', 'true' if value else 'false', ids)


def _role_state(bundle, role, scope):
    if scope.subject_actor_id is None:
        return ConditionMapping('', 'unknown', (), 'subject_actor_not_established')
    actor = bundle.actor(scope.subject_actor_id)
    if actor is None:
        return ConditionMapping('', 'unknown', (), 'unknown_actor')
    evidence = tuple(i for i in actor.fact_ids if bundle.fact(i).status != 'unknown') or tuple(f.fact_id for f in bundle.facts
                                       if f.actor_id == actor.actor_id and f.status != 'unknown')
    if not evidence:
        return ConditionMapping('', 'unknown', (), 'role_without_fact_evidence')
    if bundle.role_confirmed(actor.actor_id, role):
        return ConditionMapping('', 'true', tuple(evidence))
    if actor.role_status == 'confirmed' and actor.role not in (role, 'unknown'):
        return ConditionMapping('', 'false', tuple(evidence))
    return ConditionMapping('', 'unknown', (), f'role_{actor.role_status}:{actor.role}')


def card_item_state(spec, bundle, scope):
    if spec is None:
        return ConditionMapping('', 'unknown', (), 'no_explicit_mapping')
    if 'role' in spec:
        return _role_state(bundle, spec['role'], scope)
    combine = 'all' if 'all' in spec else 'any'
    parts = [_predicate_state(bundle, r['predicate'], r['polarity'], scope) for r in spec[combine]]
    trues = [p for p in parts if p.state == 'true']
    falses = [p for p in parts if p.state == 'false']
    if combine == 'all':
        if falses:
            return ConditionMapping('', 'false', tuple(i for p in falses for i in p.fact_ids))
        if len(trues) == len(parts):
            return ConditionMapping('', 'true', tuple(i for p in trues for i in p.fact_ids))
    else:
        if trues:
            return ConditionMapping('', 'true', tuple(i for p in trues for i in p.fact_ids))
        if len(falses) == len(parts):
            return ConditionMapping('', 'false', tuple(i for p in falses for i in p.fact_ids))
    return ConditionMapping('', 'unknown', (), ';'.join(p.reason for p in parts if p.state == 'unknown'))


def apply_card(card, bundle, scope):
    """(items, mapping, modality) for one card in one scope."""
    condition_map = card.condition_map or {}
    items = [RequirementItem(c.id, 'condition', c.question_ru, True,
                             (condition_map.get(c.id) or {}).get('facet', 'breach'))
             for c in card.conditions]
    items += [RequirementItem(e.id, 'exception', e.question_ru, True) for e in card.exceptions]
    mapping = []
    for item in items:
        state = card_item_state(condition_map.get(item.item_id), bundle, scope)
        mapping.append(ConditionMapping(item.item_id, state.state, tuple(dict.fromkeys(state.fact_ids)), state.reason))
    return items, mapping, MODALITY_BY_KIND[card.kind]


# Reading path (call A) -------------------------------------------------------

def _norm_ws(text):
    return re.sub(r'\s+', ' ', text).strip()


def locate(quote, text):
    """Character span of `quote` in `text` up to whitespace differences, or None."""
    if not isinstance(quote, str) or len(_norm_ws(quote)) < MIN_QUOTE_CHARS:
        return None
    pattern = r'\s+'.join(re.escape(w) for w in _norm_ws(quote).split(' '))
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None


def marker_segments(text):
    """Sentences / list lines of a norm that contain an exception or permission marker."""
    segments = []
    for match in re.finditer(r'[^.;\n]+[.;\n]?', text):
        lowered = match.group(0).lower()
        # A prohibition ('не допускается') is not a permission exception.
        lowered = re.sub(r'\bне\s+допускается\b', '', lowered)
        if any(m in lowered for m in EXCEPTION_MARKERS) and len(match.group(0).strip()) >= MIN_QUOTE_CHARS:
            segments.append((match.start(), match.end()))
    return segments


@dataclass
class ValidatedReading:
    relevant: bool
    modality: str | None
    requirement: str
    items: list
    links: dict                    # item_id -> [('fact', fact_id, relation) | ('role', actor_id, role)]
    exception_sources: dict        # item_id -> (node_id, start, end)
    accounted_segments: list
    errors: list


def validate_reading(raw, parent, context_items, bundle):
    """Check a call-A answer against the packet and the bundle; never repairs it silently."""
    errors = []
    if not isinstance(raw, dict):
        return ValidatedReading(False, None, '', [], {}, {}, [], ['answer is not a JSON object'])
    expected = {'relevant', 'modality', 'modality_quote', 'requirement', 'conditions', 'exceptions',
                'unused_exception_segments'}
    if set(raw) != expected:
        errors.append(f'keys must be exactly {sorted(expected)}; got {sorted(raw)}')
        return ValidatedReading(False, None, '', [], {}, {}, [], errors)
    text = parent['text']
    if raw['relevant'] is False:
        return ValidatedReading(False, None, '', [], {}, {}, [], [])
    if raw['relevant'] is not True:
        errors.append('relevant must be true or false')
    modality = raw['modality']
    if modality not in MODALITIES:
        errors.append(f'modality must be one of {MODALITIES}')
    span = locate(raw['modality_quote'], text)
    if span is None:
        errors.append('modality_quote is not an exact quote of the norm')
    else:
        cue = any(c in text[span[0]:span[1]].lower() for c in PROHIBITION_CUES)
        if modality == 'prohibition' and not cue:
            errors.append('modality prohibition, but modality_quote has no prohibition wording')
        if modality in ('obligation', 'permission') and cue:
            errors.append(f'modality {modality}, but modality_quote contains prohibition wording')
    requirement = raw['requirement'] if isinstance(raw['requirement'], str) else ''
    if not requirement.strip() or len(requirement) > 600:
        errors.append('requirement must be a non-empty sentence of at most 600 characters')
    fact_ids = {f.fact_id for f in bundle.facts}
    actor_ids = {a.actor_id for a in bundle.actors}
    items, links, sources, seen = [], {}, {}, set()
    sources_text = {parent['node_id']: text} | {c['node_id']: c['text'] for c in context_items}

    def parse_links(entry, where):
        result = []
        fact_links = entry.get('facts', [])
        if not isinstance(fact_links, list):
            errors.append(f'{where}: facts must be a list')
            return result
        for link in fact_links:
            if not isinstance(link, dict) or set(link) != {'fact_id', 'relation'}:
                errors.append(f'{where}: fact link needs fact_id and relation')
            elif not isinstance(link['fact_id'], str) or link['fact_id'] not in fact_ids:
                errors.append(f'{where}: unknown fact {link["fact_id"]}')
            elif link['relation'] not in ('same', 'opposite'):
                errors.append(f'{where}: relation must be same or opposite')
            else:
                result.append(('fact', link['fact_id'], link['relation']))
        role = entry.get('role')
        if role is not None:
            if not isinstance(role, dict) or set(role) != {'actor_id', 'role'} or not isinstance(role.get('actor_id'), str) or role.get('actor_id') not in actor_ids or role.get('role') not in ROLES:
                errors.append(f'{where}: role link needs a known actor_id and a role from {ROLES}')
            else:
                result.append(('role', role['actor_id'], role['role']))
        return result

    for kind, key in (('condition', 'conditions'), ('exception', 'exceptions')):
        if not isinstance(raw[key], list):
            errors.append(f'{key} must be a list')
            continue
        for n, entry in enumerate(raw[key]):
            where = f'{key}[{n}]'
            allowed = {'id', 'text', 'quote', 'facts', 'role'} | ({'facet'} if kind == 'condition' else {'source'})
            if not isinstance(entry, dict) or not {'id', 'text', 'quote'} <= set(entry) or set(entry) - allowed:
                errors.append(f'{where}: keys must be within {sorted(allowed)} and include id, text, quote')
                continue
            item_id = entry['id']
            if not isinstance(item_id, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,30}', item_id) or item_id in seen:
                errors.append(f'{where}: id must be a unique short snake_case identifier')
                continue
            seen.add(item_id)
            node = entry.get('source', parent['node_id']) if kind == 'exception' else parent['node_id']
            if not isinstance(node, str) or node not in sources_text:
                errors.append(f'{where}: source {node} is not in the packet')
                continue
            quote_span = locate(entry['quote'], sources_text[node])
            if quote_span is None:
                errors.append(f'{where}: quote is not an exact quote of {node}')
                continue
            facet = entry.get('facet', 'breach')
            if kind == 'condition' and facet not in FACETS:
                errors.append(f'{where}: facet must be one of {FACETS}')
                continue
            if not isinstance(entry['text'], str) or not entry['text'].strip() or len(entry['text']) > 300:
                errors.append(f'{where}: text must be a short non-empty statement')
                continue
            items.append(RequirementItem(item_id, kind, entry['text'].strip(), True, facet if kind == 'condition' else 'breach',
                                         quote_span if node == parent['node_id'] else None))
            links[item_id] = parse_links(entry, where)
            sources[item_id] = (node, *quote_span)
    if not any(i.kind == 'condition' for i in items) and not errors:
        errors.append('a relevant norm needs at least one condition')
    accounted = []
    unused = raw['unused_exception_segments']
    if not isinstance(unused, list):
        errors.append('unused_exception_segments must be a list')
        unused = []
    for n, entry in enumerate(unused):
        if not isinstance(entry, dict) or set(entry) != {'quote', 'source', 'why'}:
            errors.append(f'unused_exception_segments[{n}]: keys quote, source, why')
            continue
        node_text = sources_text.get(entry['source']) if isinstance(entry['source'], str) else None
        found = locate(entry['quote'], node_text) if node_text else None
        if found is None:
            errors.append(f'unused_exception_segments[{n}]: quote is not exact in {entry["source"]}')
        elif not str(entry['why']).strip():
            errors.append(f'unused_exception_segments[{n}]: why must explain the irrelevance')
        else:
            accounted.append((entry['source'], *found))
    # Deterministic segment accounting: every exception/permission segment of the norm and of the
    # exception-context provisions is either read as an exception or explicitly declared unused.
    covered = [sources[i.item_id] for i in items if i.kind == 'exception'] + accounted
    if span and modality == 'permission':
        covered.append((parent['node_id'], *span))
    for node, node_text in sources_text.items():
        for start, end in marker_segments(node_text):
            if not any(n == node and s < end and start < e for n, s, e in covered):
                errors.append(f'exception segment not accounted for in {node}: "{_norm_ws(node_text[start:end])[:90]}"')
    return ValidatedReading(True, modality, requirement.strip(), items, links, sources, accounted, errors)


def reading_states(reading, bundle):
    """States of reading items, computed from original fact statuses and link polarity."""
    mapping = []
    for item in reading.items:
        values, ids, decided_facts = [], [], []
        for link in reading.links.get(item.item_id, []):
            if link[0] == 'role':
                _, actor_id, role = link
                state = _role_state(bundle, role, Scope(actor_id, None))
                if state.state != 'unknown':
                    values.append(state.state == 'true')
                    ids += state.fact_ids
                continue
            _, fact_id, relation = link
            fact = bundle.fact(fact_id)
            if fact.status == 'unknown':
                continue
            holds = fact.status == 'confirmed'
            values.append(holds if relation == 'same' else not holds)
            ids.append(fact_id)
            decided_facts.append((fact, holds if relation == 'same' else not holds))
        if not values:
            mapping.append(ConditionMapping(item.item_id, 'unknown', (), 'no_decided_linked_fact'))
        elif len({f.actor_id for f, _ in decided_facts if f.actor_id is not None}) > 1 or \
                len({f.operation_id for f, _ in decided_facts if f.operation_id is not None}) > 1 or \
                len({f.object for f, _ in decided_facts if f.object is not None}) > 1:
            mapping.append(ConditionMapping(item.item_id, 'unknown', (), 'mixed_fact_scopes'))
        elif len(set(values)) == 1:
            mapping.append(ConditionMapping(item.item_id, 'true' if values[0] else 'false', tuple(dict.fromkeys(ids))))
        else:
            # Linked facts disagree: a conflict if they overlap in time, otherwise the scope is unclear.
            pseudo = [replace(f, status='confirmed' if v else 'refuted') for f, v in decided_facts]
            mapping.append(ConditionMapping(item.item_id, 'unknown', (), combine_states(pseudo).status))
    return mapping


# Decision ----------------------------------------------------------------------

def decide(items, mapping, completeness, basis, modality=None):
    """(decision, reasons). Order: scope, exception, breach, then the complete positive case.

    completeness: the packet's per-norm record; basis: (allowed, reason) for using the source as a basis.
    """
    states = {m.item_id: m.state for m in mapping}
    if modality == 'permission':
        return 'not_applicable_scope', ['permission_does_not_create_a_breach']
    conditions = [i for i in items if i.kind == 'condition']
    exceptions = [i for i in items if i.kind == 'exception']
    scope_false = [i.item_id for i in conditions if i.facet == 'scope' and states.get(i.item_id) == 'false']
    if scope_false:
        return 'not_applicable_scope', [f'scope_condition_false:{x}' for x in scope_false]
    exception_true = [i.item_id for i in exceptions if states.get(i.item_id) == 'true']
    if exception_true:
        return 'exception_applies', [f'exception_true:{x}' for x in exception_true]
    breach_false = [i.item_id for i in conditions if i.facet == 'breach' and states.get(i.item_id) == 'false']
    if breach_false:
        return 'refuted', [f'breach_condition_false:{x}' for x in breach_false]
    reasons = []
    if not any(i.facet == 'breach' for i in conditions):
        reasons.append('no_breach_condition')
    reasons += [f'condition_{states.get(i.item_id, "unknown")}:{i.item_id}' for i in conditions
                if i.required and states.get(i.item_id) != 'true']
    reasons += [f'exception_not_excluded:{i.item_id}' for i in exceptions if states.get(i.item_id) != 'false']
    if not completeness.get('complete', False):
        reasons += ['context_incomplete:' + r for r in completeness.get('incomplete_reasons', [])] or ['context_incomplete']
    if not basis[0]:
        reasons.append('basis_not_allowed:' + basis[1])
    return ('insufficient', reasons) if reasons else ('violation_supported', [])


def basis_allowed(item):
    """Only an operational source in force at the snapshot may ground a violation."""
    if item['role'] != 'operational':
        return False, 'source_role_' + item['role']
    if item['status'] != 'in_force_at_snapshot':
        return False, 'unit_status_' + item['status']
    return True, None
