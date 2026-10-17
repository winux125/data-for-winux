"""Strict input/output contracts of the legal RAG layer (stdlib only).

Input: structured observations produced by an external video module. The RAG layer
never re-detects actions and never turns classifier scores into facts, so any
classifier-like field is rejected. A predicate that is absent is `unknown`, never
`false`. A refuted fact keeps its negative polarity everywhere, including the text
used for retrieval; retrieval text never replaces the original fact and status.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re

INPUT_SCHEMA = 'legal_rag.input.v1'
OUTPUT_SCHEMA = 'legal_rag.output.v1'

FACT_STATUSES = ('confirmed', 'refuted', 'unknown')
ROLE_STATUSES = ('confirmed', 'inferred', 'unknown')
ROLES = ('cashier', 'client', 'collector', 'controller', 'other_staff', 'other', 'unknown')
ORGANIZATIONS = ('bank', 'exchange_office', 'collection_organization', 'postal_operator', 'unknown')
DECISIONS = ('violation_supported', 'refuted', 'exception_applies', 'insufficient', 'not_applicable_scope', 'no_norm')
CONDITION_STATES = ('true', 'false', 'unknown')
# scope: who/what situation the norm addresses (false -> not applicable);
# breach: the act or omission itself (false -> refuted);
# evidence: whether the observation can establish the breach at all (false -> insufficient).
FACETS = ('scope', 'breach', 'evidence')
SENTENCE_KINDS = ('observation', 'requirement', 'interpretation', 'mapping', 'conclusion', 'limitation')
CITATION_LEVELS = ('clause', 'unit', 'document')
# Scores, labels or verdicts from a classifier are not observations.
FORBIDDEN_KEYS = frozenset({'label', 'labels', 'score', 'scores', 'probability', 'probabilities', 'confidence',
                            'logit', 'logits', 'prediction', 'predictions', 'verdict', 'classifier', 'jepa'})
ID = re.compile(r'[A-Za-z][A-Za-z0-9_.:-]{0,63}')
PREDICATE = re.compile(r'[a-z][a-z0-9_]{1,63}')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


class ContractError(ValueError):
    pass


def _forbid_classifier_fields(value, path='$'):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ContractError(f'{path}.{key}: classifier outputs are not accepted as observations')
            _forbid_classifier_fields(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _forbid_classifier_fields(item, f'{path}[{index}]')


def _keys(obj, required, optional, where):
    if not isinstance(obj, dict):
        raise ContractError(f'{where}: expected an object')
    missing = set(required) - set(obj)
    extra = set(obj) - set(required) - set(optional)
    if missing or extra:
        raise ContractError(f'{where}: missing {sorted(missing)}, unexpected {sorted(extra)}')


def _id(value, where):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ContractError(f'{where}: invalid identifier {value!r}')
    return value


def _text(value, where, allow_empty=False, limit=500):
    if not isinstance(value, str) or (not allow_empty and not value.strip()) or len(value) > limit:
        raise ContractError(f'{where}: expected text of at most {limit} characters')
    return value.strip()


def _time(value, where):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ContractError(f'{where}: expected a non-negative number of seconds or null')
    return float(value)


def _refs(value, where):
    if not isinstance(value, list) or any(not isinstance(r, str) or not r.strip() for r in value):
        raise ContractError(f'{where}: evidence_refs must be a list of non-empty strings')
    if len(value) != len(set(value)):
        raise ContractError(f'{where}: duplicate evidence reference')
    return tuple(value)


@dataclass(frozen=True)
class Context:
    organization_type: str = 'unknown'
    operation: str | None = None
    location: str | None = None
    event_date: str | None = None     # unknown dates stay null; never inferred from upload time


@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: str
    role_status: str
    fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Fact:
    fact_id: str
    predicate: str
    statement: str                    # neutral proposition; its truth is given ONLY by `status`
    status: str
    actor_id: str | None = None
    object: str | None = None
    operation_id: str | None = None   # scope: which operation/event the fact belongs to
    t_start: float | None = None
    t_end: float | None = None
    anchor_sec: float | None = None
    evidence_refs: tuple[str, ...] = ()
    source: str = 'external_video_module'


@dataclass(frozen=True)
class FreeObservation:
    observation_id: str
    text: str
    status: str
    evidence_refs: tuple[str, ...] = ()
    source: str = 'external_video_module'


@dataclass(frozen=True)
class QueryPart:
    """Retrieval text derived from one fact; `status` and `fact_id` travel with it."""
    text: str
    status: str
    origin_id: str
    origin: str                       # fact | free_observation
    predicate: str | None


@dataclass(frozen=True)
class FactState:
    # confirmed | refuted | unknown
    # conflict:       different decided statuses on overlapping intervals of the same scope
    # scope_required: different decided statuses whose simultaneity is not established
    #                 (disjoint intervals or missing times); the caller must narrow the scope
    status: str
    fact_ids: tuple[str, ...]


def _overlap(a, b):
    """True/False when both intervals are known, None when simultaneity cannot be established."""
    if a.t_start is None or a.t_end is None or b.t_start is None or b.t_end is None:
        return None
    return a.t_start <= b.t_end and b.t_start <= a.t_end


def combine_states(facts):
    """FactState of facts about one proposition (see ObservationBundle.state)."""
    ids = tuple(f.fact_id for f in facts)
    decided = [f for f in facts if f.status != 'unknown']
    statuses = {f.status for f in decided}
    if not statuses:
        return FactState('unknown', ids)
    if len(statuses) == 1:
        return FactState(statuses.pop(), ids)
    pairs = [(a, b) for a in decided for b in decided if a.status == 'confirmed' and b.status == 'refuted']
    if any(_overlap(a, b) for a, b in pairs):
        return FactState('conflict', ids)
    return FactState('scope_required', ids)


@dataclass(frozen=True)
class ObservationBundle:
    bundle_id: str
    context: Context
    actors: tuple[Actor, ...]
    facts: tuple[Fact, ...]
    free_observations: tuple[FreeObservation, ...]
    provenance: dict = field(default_factory=dict)

    def actor(self, actor_id):
        return next((a for a in self.actors if a.actor_id == actor_id), None)

    def fact(self, fact_id):
        return next((f for f in self.facts if f.fact_id == fact_id), None)

    def state(self, predicate, actor_id=None, operation_id=None, object=None, window=None):
        """Status of a predicate within a scope (actor, operation, object, time window).

        Absent means unknown. Facts with different decided statuses are a conflict only
        when they overlap in time; otherwise, or when times are missing, the result is
        scope_required — a sequence of events is never silently read as simultaneous.
        A window keeps facts overlapping it; untimed facts cannot be placed in a window.
        """
        matching = []
        for f in self.facts:
            if f.predicate != predicate:
                continue
            if any(want is not None and have != want for want, have in
                   ((actor_id, f.actor_id), (operation_id, f.operation_id), (object, f.object))):
                continue
            if window is not None:
                if f.t_start is None or f.t_end is None or not (f.t_start <= window[1] and window[0] <= f.t_end):
                    continue
            matching.append(f)
        return combine_states(matching)

    def role_confirmed(self, actor_id, role):
        """Only a confirmed role satisfies a role condition; inferred or unknown roles do not."""
        actor = self.actor(actor_id)
        return actor is not None and actor.role == role and actor.role_status == 'confirmed'

    def query_parts(self):
        """Retrieval text that preserves polarity: refuted is negated, unknown is a question."""
        parts = []
        for fact in self.facts:
            prefix = {'confirmed': '', 'refuted': 'не выполнено: ', 'unknown': 'не установлено: '}[fact.status]
            parts.append(QueryPart(prefix + fact.statement, fact.status, fact.fact_id, 'fact', fact.predicate))
        for observation in self.free_observations:
            prefix = {'confirmed': '', 'refuted': 'не выполнено: ', 'unknown': 'не установлено: '}[observation.status]
            parts.append(QueryPart(prefix + observation.text, observation.status, observation.observation_id,
                                   'free_observation', None))
        return parts

    def to_dict(self):
        return dict(schema=INPUT_SCHEMA, **asdict(self))


def parse_input(raw):
    """Validate and freeze an input bundle; raise ContractError on any violation."""
    _forbid_classifier_fields(raw)
    _keys(raw, {'schema', 'bundle_id', 'facts'}, {'context', 'actors', 'free_observations', 'provenance'}, '$')
    if raw['schema'] != INPUT_SCHEMA:
        raise ContractError(f'$.schema: expected {INPUT_SCHEMA}')
    context_raw = raw.get('context') or {}
    _keys(context_raw, set(), {'organization_type', 'operation', 'location', 'event_date'}, '$.context')
    organization = context_raw.get('organization_type') or 'unknown'
    if organization not in ORGANIZATIONS:
        raise ContractError(f'$.context.organization_type: one of {ORGANIZATIONS}')
    date = context_raw.get('event_date')
    if date is not None and (not isinstance(date, str) or not DATE.fullmatch(date)):
        raise ContractError('$.context.event_date: YYYY-MM-DD or null')
    context = Context(organization, context_raw.get('operation'), context_raw.get('location'), date)

    seen = set()

    def unique(value, where):
        if value in seen:
            raise ContractError(f'{where}: duplicate identifier {value}')
        seen.add(value)
        return value

    actors = []
    for i, a in enumerate(raw.get('actors') or []):
        where = f'$.actors[{i}]'
        _keys(a, {'actor_id', 'role', 'role_status'}, {'fact_ids'}, where)
        if a['role'] not in ROLES or a['role_status'] not in ROLE_STATUSES:
            raise ContractError(f'{where}: role must be one of {ROLES}, role_status one of {ROLE_STATUSES}')
        actors.append(Actor(unique(_id(a['actor_id'], where), where), a['role'], a['role_status'],
                            tuple(_id(x, where) for x in a.get('fact_ids', []))))
    actor_ids = {a.actor_id for a in actors}

    if not isinstance(raw['facts'], list):
        raise ContractError('$.facts: expected a list')
    facts = []
    for i, f in enumerate(raw['facts']):
        where = f'$.facts[{i}]'
        _keys(f, {'fact_id', 'predicate', 'statement', 'status'},
              {'actor_id', 'object', 'operation_id', 't_start', 't_end', 'anchor_sec', 'evidence_refs', 'source'}, where)
        if not isinstance(f['predicate'], str) or not PREDICATE.fullmatch(f['predicate']):
            raise ContractError(f'{where}.predicate: snake_case predicate expected')
        if f['status'] not in FACT_STATUSES:
            raise ContractError(f'{where}.status: one of {FACT_STATUSES}')
        actor_id = f.get('actor_id')
        if actor_id is not None and actor_id not in actor_ids:
            raise ContractError(f'{where}.actor_id: unknown actor {actor_id}')
        t_start, t_end, anchor = (_time(f.get(k), f'{where}.{k}') for k in ('t_start', 't_end', 'anchor_sec'))
        if t_start is not None and t_end is not None and t_start > t_end:
            raise ContractError(f'{where}: t_start after t_end')
        if anchor is not None and ((t_start is not None and anchor < t_start) or (t_end is not None and anchor > t_end)):
            raise ContractError(f'{where}: anchor_sec outside [t_start, t_end]')
        refs = _refs(f.get('evidence_refs', []), f'{where}.evidence_refs')
        if f['status'] != 'unknown' and not refs:
            # A refuted fact claims an observed absence; it needs evidence of the inspected interval.
            raise ContractError(f'{where}: {f["status"]} facts need evidence_refs')
        operation_id = f.get('operation_id')
        if operation_id is not None:
            _id(operation_id, f'{where}.operation_id')
        facts.append(Fact(unique(_id(f['fact_id'], where), where), f['predicate'],
                          _text(f['statement'], f'{where}.statement'), f['status'], actor_id,
                          f.get('object'), operation_id, t_start, t_end, anchor, refs,
                          f.get('source') or 'external_video_module'))

    observations = []
    for i, o in enumerate(raw.get('free_observations') or []):
        where = f'$.free_observations[{i}]'
        _keys(o, {'observation_id', 'text', 'status'}, {'evidence_refs', 'source'}, where)
        if o['status'] not in FACT_STATUSES:
            raise ContractError(f'{where}.status: one of {FACT_STATUSES}')
        refs = _refs(o.get('evidence_refs', []), f'{where}.evidence_refs')
        if o['status'] != 'unknown' and not refs:
            raise ContractError(f'{where}: {o["status"]} observations need evidence_refs')
        observations.append(FreeObservation(unique(_id(o['observation_id'], where), where),
                                            _text(o['text'], f'{where}.text'), o['status'], refs,
                                            o.get('source') or 'external_video_module'))
    fact_ids = {f.fact_id for f in facts}
    for actor in actors:
        if set(actor.fact_ids) - fact_ids:
            raise ContractError(f'actor {actor.actor_id}: references unknown facts')
    return ObservationBundle(_id(raw['bundle_id'], '$.bundle_id'), context, tuple(actors), tuple(facts),
                             tuple(observations), dict(raw.get('provenance') or {}))


# Output ----------------------------------------------------------------------

@dataclass
class NormRef:
    norm_id: str
    source_id: str
    title: str
    official_url: str
    citation_level: str
    unit_label: str | None
    quote: str
    quote_sha256: str
    lines: tuple[int, int]
    status: str
    revision: str | None


@dataclass
class RequirementItem:
    item_id: str
    kind: str                         # condition | exception
    text: str
    required: bool = True
    facet: str = 'breach'             # conditions only, see FACETS
    quote_span: tuple[int, int] | None = None   # character offsets in NormRef.quote


@dataclass
class ConditionMapping:
    item_id: str
    state: str                        # true | false | unknown
    fact_ids: tuple[str, ...] = ()
    reason: str | None = None         # why a state stayed unknown (no_mapping, conflict, scope_required, ...)


@dataclass
class Sentence:
    sentence_id: str
    kind: str
    text: str
    fact_ids: tuple[str, ...] = ()
    quote_span_ids: tuple[str, ...] = ()


@dataclass
class NormAssessment:
    norm: NormRef
    modality: str                     # prohibition | obligation | permission
    items: list[RequirementItem]
    mapping: list[ConditionMapping]
    decision: str
    missing: list[str]
    requirement_source: str           # card | llm_reading_validated
    context_completeness: dict
    sentences: list[Sentence] = field(default_factory=list)
    explanation_text: str = ''
    generator: str = ''
    publishable: dict = field(default_factory=dict)
    decision_reasons: list = field(default_factory=list)
    evidence: list = field(default_factory=list)       # cited facts with times and evidence_refs (code-built)
    validation: dict = field(default_factory=dict)     # call A / call B validation records
    rule_id: str | None = None
    supporting_norms: list = field(default_factory=list)  # exact packet sources used for conditions/exceptions


@dataclass
class LegalAssessment:
    bundle_id: str
    assessments: list[NormAssessment]
    no_norm: dict | None = None
    versions: dict = field(default_factory=dict)
    timings_ms: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)

    def to_dict(self):
        return dict(schema=OUTPUT_SCHEMA, **asdict(self))


def validate_output(result, bundle):
    """Structural invariants of an output; semantic checks of text live in validate.py."""
    fact_ids = {f.fact_id for f in bundle.facts} | {o.observation_id for o in bundle.free_observations}
    if result.bundle_id != bundle.bundle_id:
        raise ContractError('Output belongs to another bundle')
    if not result.assessments and not result.no_norm:
        raise ContractError('Either assessments or a no_norm reason is required')
    for a in result.assessments:
        where = a.norm.norm_id
        if a.decision not in DECISIONS or a.norm.citation_level not in CITATION_LEVELS:
            raise ContractError(f'{where}: invalid decision or citation level')
        items = {i.item_id: i for i in a.items}
        if len(items) != len(a.items):
            raise ContractError(f'{where}: duplicate requirement item IDs')
        if any(i.kind not in ('condition', 'exception') for i in a.items):
            raise ContractError(f'{where}: requirement items must be conditions or exceptions')
        if any(i.kind == 'condition' and i.facet not in FACETS for i in a.items):
            raise ContractError(f'{where}: condition facet must be one of {FACETS}')
        states = {}
        for m in a.mapping:
            if m.item_id not in items or m.state not in CONDITION_STATES or m.item_id in states:
                raise ContractError(f'{where}: invalid or duplicate mapping for {m.item_id}')
            if set(m.fact_ids) - fact_ids:
                raise ContractError(f'{where}: mapping cites unknown facts')
            if m.state != 'unknown' and not m.fact_ids:
                raise ContractError(f'{where}: decided state of {m.item_id} must cite facts')
            states[m.item_id] = m.state
        for item in a.items:
            if item.quote_span is not None:
                start, end = item.quote_span
                if not 0 <= start < end <= len(a.norm.quote):
                    raise ContractError(f'{where}: quote span of {item.item_id} outside the quote')
        if a.decision == 'violation_supported':
            required = [i for i in a.items if i.kind == 'condition' and i.required]
            if not required:
                raise ContractError(f'{where}: violation_supported needs at least one required condition')
            unmapped = [i.item_id for i in a.items if i.item_id not in states]
            if unmapped:
                raise ContractError(f'{where}: violation_supported with unmapped items {unmapped}')
            open_conditions = [i for i in required if states[i.item_id] != 'true']
            open_exceptions = [i for i in a.items if i.kind == 'exception' and states[i.item_id] != 'false']
            if open_conditions or open_exceptions or not a.context_completeness.get('complete', False):
                raise ContractError(f'{where}: violation_supported with open conditions, exceptions or context')
        for s in a.sentences:
            if s.kind not in SENTENCE_KINDS or set(s.fact_ids) - fact_ids:
                raise ContractError(f'{where}: sentence {s.sentence_id} has invalid kind or facts')
    return result
