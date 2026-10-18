"""Formal assessment of a rule card against visual evidence, and the publication gate.

Layers: L1 visual states come from the verifier; L2 `assess` applies the card;
L3 `applicability` declares (never invents) the edition assumption; L4
`publishable` is the single place where review flags and clause status are enforced.
`not_visible` is never converted to `false`.
"""
from __future__ import annotations

from .types import STATES, Assessment

POLICIES = ('strict', 'p_core')


def assess(card, states, policy='strict'):
    if policy not in POLICIES:
        raise ValueError('Unknown policy ' + str(policy))
    known = card.condition_ids() + card.exception_ids()
    extra = sorted(set(states) - set(known))
    if extra:
        raise ValueError(f'{card.rule_id}: evidence for unknown conditions {extra}')
    if any(v not in STATES for v in states.values()):
        raise ValueError(f'{card.rule_id}: states must be one of {STATES}')
    full = {k: states.get(k, 'not_visible') for k in known}
    result = Assessment(rule_id=card.rule_id, l2='insufficient', policy=policy, states=full,
                        missing=[k for k in known if k not in states])
    result.refuted_by = [c.id for c in card.conditions if full[c.id] == 'false']
    result.exception_hits = [e.id for e in card.exceptions if full[e.id] == 'true']
    if result.refuted_by:
        result.l2 = 'refuted'
        return result
    if result.exception_hits:
        result.l2 = 'not_applicable'
        return result
    core_open = [c.id for c in card.conditions if c.tier == 'core' and full[c.id] != 'true']
    context_open = [c.id for c in card.conditions if c.tier == 'context' and full[c.id] != 'true']
    exceptions_open = [e.id for e in card.exceptions if full[e.id] != 'false']
    if core_open or exceptions_open or (context_open and policy == 'strict'):
        result.unresolved = core_open + exceptions_open + context_open
        return result
    result.l2 = 'matched'
    result.caveats = context_open
    return result


def applicability(card, corpus):
    """Declared edition assumption; the video date is unknown and is never invented."""
    clauses, warnings = [], []
    for clause_id in card.clause_ids + card.related_clause_ids:
        clause = corpus.clause(clause_id)
        last = max((a for a in clause.amendments if a.act_date), key=lambda a: a.act_date, default=None)
        clauses.append(dict(clause_id=clause_id, status=clause.status,
                            last_amendment=None if last is None else dict(
                                act_date=last.act_date, act_number=last.act_number, kind=last.kind,
                                effective_from=last.effective_from, suspended_until=last.suspended_until)))
        if clause.status != 'in_force_at_snapshot':
            warnings.append(f'{clause_id}: {clause.status}')
    acts = sorted({c.split(':')[0] for c in card.clause_ids + card.related_clause_ids})
    return dict(basis='assumed_in_force_at_snapshot', event_date_known=False, clauses=clauses, warnings=warnings,
                acts={sid: dict(revision_instant=corpus.acts[sid].revision_instant,
                                retrieved_utc=corpus.acts[sid].retrieved_utc) for sid in acts})


def publishable(card, assessment, corpus, mode='service'):
    """Return (allowed, reason). Only 'service' mode output may reach the competition API."""
    if mode not in ('service', 'dev'):
        raise ValueError('mode must be service or dev')
    if assessment.rule_id != card.rule_id:
        raise ValueError('Assessment belongs to another card')
    if assessment.l2 != 'matched':
        return False, 'l2_' + assessment.l2
    for clause_id in card.clause_ids:
        clause = corpus.clause(clause_id)
        if card.pinned_text_sha256.get(clause_id) != clause.text_sha256:
            return False, 'pinned_text_changed:' + clause_id
        if clause.status != 'in_force_at_snapshot':
            return False, f'clause_{clause.status}:{clause_id}'
    if mode == 'dev':
        return True, 'dev_only'
    if not (card.review.production_active and card.review.human_reviewed):
        return False, 'rule_not_production_active'
    return True, None
