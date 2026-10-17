"""Rule cards: which visual conditions a human formalized for exact corpus clauses.

A card holds no legal text of its own. It points at corpus clauses and pins their
SHA256, so a changed snapshot invalidates the card instead of silently drifting.
`production_active` requires an explicit human review record.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from .types import Condition, Exception_, Review, RuleCard

DEFAULT_CARDS = Path(__file__).resolve().parent / 'data' / 'rule_cards.json'
CARD_FIELDS = {'rule_id', 'type_label_ru', 'kind', 'clause_ids', 'related_clause_ids', 'pinned_text_sha256',
               'conditions', 'exceptions', 'non_visual', 'trigger_predicates', 'anchor_policy', 'review',
               'condition_map'}
REVIEW_FIELDS = {'text_verified_by', 'logic_reviewed_by', 'reviewed_at', 'human_reviewed', 'production_active'}
KINDS = {'commission', 'omission', 'state'}
ANCHORS = {'onset', 'handover_moment', 'state_first_visible', 'phase_end'}
TIERS = {'core', 'context'}
FACETS = ('scope', 'breach', 'evidence')
ID = re.compile(r'[a-z][a-z0-9_]{1,60}')


class CardError(ValueError):
    pass


def _review(raw, rule_id):
    if set(raw) != REVIEW_FIELDS:
        raise CardError(f'{rule_id}: review must have exactly {sorted(REVIEW_FIELDS)}')
    review = Review(**raw)
    if not isinstance(review.human_reviewed, bool) or not isinstance(review.production_active, bool):
        raise CardError(f'{rule_id}: review flags must be JSON booleans')
    if review.production_active and not (review.human_reviewed and review.text_verified_by
                                         and review.logic_reviewed_by and review.reviewed_at):
        raise CardError(f'{rule_id}: production_active requires a complete human review record')
    if review.human_reviewed and not (review.logic_reviewed_by and review.reviewed_at):
        raise CardError(f'{rule_id}: human_reviewed requires reviewer and date')
    return review


def _condition_map(raw, condition_ids, exception_ids, predicates, rule_id):
    """Explicit mapping of card conditions/exceptions to fact predicates; unmapped items stay unknown.

    A condition spec carries its facet (scope | breach | evidence); an exception spec has none.
    """
    if not isinstance(raw, dict) or set(raw) - condition_ids - exception_ids:
        raise CardError(f'{rule_id}: condition_map keys must be condition/exception IDs of the card')
    for item_id, spec in raw.items():
        facet = spec.get('facet')
        if item_id in condition_ids and facet not in FACETS:
            raise CardError(f'{rule_id}.{item_id}: condition mapping needs a facet from {FACETS}')
        if item_id in exception_ids and facet is not None:
            raise CardError(f'{rule_id}.{item_id}: exceptions have no facet')
        body = {k: v for k, v in spec.items() if k != 'facet'}
        if set(body) == {'role'} and isinstance(body['role'], str):
            continue
        if len(body) != 1 or next(iter(body)) not in ('all', 'any') or not body[next(iter(body))]:
            raise CardError(f'{rule_id}.{item_id}: mapping must be {{role}}, {{all: [...]}} or {{any: [...]}}')
        for req in next(iter(body.values())):
            if set(req) != {'predicate', 'polarity'} or req['polarity'] not in ('positive', 'negative'):
                raise CardError(f'{rule_id}.{item_id}: requirement needs predicate and polarity')
            if req['predicate'] not in predicates:
                raise CardError(f'{rule_id}.{item_id}: predicate {req["predicate"]} outside the vocabulary')
    return dict(raw)


def load_cards(corpus, path=DEFAULT_CARDS):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('cards'), list):
        raise CardError('Invalid rule card file schema')
    vocabulary = data.get('predicate_vocabulary', {})
    predicates = set(vocabulary.get('canonical', []))
    cards = {}
    for raw in data['cards']:
        rule_id = raw.get('rule_id', '?')
        if set(raw) != CARD_FIELDS:
            raise CardError(f'{rule_id}: card fields differ from schema')
        if rule_id in cards:
            raise CardError('Duplicate rule_id ' + rule_id)
        if raw['kind'] not in KINDS or raw['anchor_policy'] not in ANCHORS:
            raise CardError(f'{rule_id}: unknown kind or anchor_policy')
        if not raw['clause_ids']:
            raise CardError(f'{rule_id}: needs at least one primary clause')
        for clause_id in raw['clause_ids'] + raw['related_clause_ids']:
            if clause_id not in corpus.clauses:
                raise CardError(f'{rule_id}: unknown clause {clause_id}')
        for clause_id in raw['clause_ids']:
            clause = corpus.clauses[clause_id]
            if clause.status == 'repealed':
                raise CardError(f'{rule_id}: primary clause {clause_id} is repealed')
            if raw['pinned_text_sha256'].get(clause_id) != clause.text_sha256:
                raise CardError(f'{rule_id}: pinned text hash of {clause_id} differs from the verified snapshot')
        if set(raw['pinned_text_sha256']) != set(raw['clause_ids']):
            raise CardError(f'{rule_id}: pin exactly the primary clauses')
        conditions = tuple(Condition(**c) for c in raw['conditions'])
        exceptions = tuple(Exception_(**e) for e in raw['exceptions'])
        ids = [c.id for c in conditions] + [e.id for e in exceptions]
        if len(ids) != len(set(ids)) or any(not ID.fullmatch(i) for i in ids):
            raise CardError(f'{rule_id}: condition/exception IDs must be unique snake_case')
        if not any(c.tier == 'core' for c in conditions) or any(c.tier not in TIERS for c in conditions):
            raise CardError(f'{rule_id}: needs core conditions and valid tiers')
        allowed_sources = set(raw['clause_ids']) | set(raw['related_clause_ids'])
        if any(e.source_clause_id not in allowed_sources for e in exceptions):
            raise CardError(f'{rule_id}: an exception must cite a primary or related clause')
        if any(not q.question_ru.strip() for q in conditions + exceptions):
            raise CardError(f'{rule_id}: empty question')
        unknown = set(raw['trigger_predicates']) - predicates
        if unknown:
            raise CardError(f'{rule_id}: trigger predicates outside the vocabulary: {sorted(unknown)}')
        condition_map = _condition_map(raw['condition_map'], {c.id for c in conditions},
                                       {e.id for e in exceptions}, predicates, rule_id)
        cards[rule_id] = RuleCard(
            rule_id=rule_id, type_label_ru=raw['type_label_ru'], kind=raw['kind'],
            clause_ids=tuple(raw['clause_ids']), related_clause_ids=tuple(raw['related_clause_ids']),
            pinned_text_sha256=dict(raw['pinned_text_sha256']), conditions=conditions, exceptions=exceptions,
            non_visual=tuple(raw['non_visual']), trigger_predicates=tuple(raw['trigger_predicates']),
            anchor_policy=raw['anchor_policy'], review=_review(raw['review'], rule_id),
            condition_map=condition_map)
    return cards, dict(status=data.get('status'), predicate_vocabulary=vocabulary)
