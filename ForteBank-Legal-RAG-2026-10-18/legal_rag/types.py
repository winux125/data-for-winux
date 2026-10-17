"""Typed records of the legal RAG layer. Texts are exact source spans, never paraphrases."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

State = Literal['true', 'false', 'not_visible']
STATES = ('true', 'false', 'not_visible')


@dataclass(frozen=True)
class Amendment:
    """One amending act mentioned in a footnote or an official suspension note."""
    kind: str                      # redaction | changes | added | excluded | suspended | other
    line: int                      # 1-based source line of the note
    raw: str                       # exact note line
    act_date: str | None = None    # ISO date of the amending resolution
    act_number: str | None = None
    effective_note: str | None = None
    effective_from: str | None = None
    suspended_until: str | None = None
    target: str | None = None      # e.g. 'подпункт 3)' for a partial suspension


@dataclass(frozen=True)
class SubItem:
    number: str
    line: int
    text: str


@dataclass(frozen=True)
class Definition:
    term: str
    key: tuple[str, ...]           # stemmed term tokens
    clause_id: str
    item: str
    line: int
    text: str


@dataclass(frozen=True)
class ActAlias:
    name: str                      # text inside '(далее – ...)'
    key: tuple[str, ...]
    target_source_id: str | None   # act in the corpus, or None if external/term
    line: int


@dataclass(frozen=True)
class Act:
    source_id: str
    number: str
    registry_number: str
    title: str
    adopted: str | None            # ISO date parsed from the official text
    official_url: str
    text_sha256: str
    revision_instant: str
    retrieved_utc: str


@dataclass(frozen=True)
class Clause:
    clause_id: str                 # '{source_id}:{number}'
    source_id: str
    number: str
    section_id: str
    headings: tuple[str, ...]
    lines: tuple[int, int]         # 1-based inclusive source lines
    text: str                      # exact lines joined with LF plus final LF
    text_sha256: str
    notes: tuple[tuple[int, str], ...]   # official notes printed before the clause
    subitems: tuple[SubItem, ...]
    amendments: tuple[Amendment, ...]
    status: str                    # in_force_at_snapshot | repealed | suspended_wording_uncertain | partially_suspended_wording_uncertain


@dataclass(frozen=True)
class Reference:
    clause_id: str
    line: int
    phrase: str
    kind: str                      # clause | subitem
    numbers: tuple[str, ...]
    parent: str | None
    resolution: str                # same_act | cross_act | implicit_same_act | self_clause | external
    target_source_id: str | None
    target_clause_ids: tuple[str, ...]
    unresolved_reason: str | None = None


@dataclass(frozen=True)
class Hit:
    clause_id: str
    score: float
    rank: int
    matched_subitem: str | None
    matched_terms: tuple[str, ...]


@dataclass
class PacketItem:
    tier: int
    kind: str                      # clause | definition | scope | alternative | preamble
    clause_id: str | None
    source_id: str
    reason: str
    text: str
    text_sha256: str
    lines: tuple[int, int]
    source_url: str
    revision_instant: str
    status: str = 'in_force_at_snapshot'
    depth: int = 0
    score: float | None = None
    amendments: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class RetrievalPacket:
    items: list[PacketItem]
    omitted: list[dict]
    unresolved: list[dict]
    coverage: dict
    needs_review: bool
    budget_chars: int
    serialized_chars: int = 0
    version: str = 'legal-rag-packet-v1'

    def clause_ids(self, tier=None):
        return [i.clause_id for i in self.items if i.clause_id and (tier is None or i.tier == tier)]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Condition:
    id: str
    question_ru: str
    tier: str                      # core | context


@dataclass(frozen=True)
class Exception_:
    id: str
    question_ru: str
    source_clause_id: str


@dataclass(frozen=True)
class Review:
    text_verified_by: str | None
    logic_reviewed_by: str | None
    reviewed_at: str | None
    human_reviewed: bool
    production_active: bool


@dataclass(frozen=True)
class RuleCard:
    rule_id: str
    type_label_ru: str
    kind: str                      # commission | omission | state
    clause_ids: tuple[str, ...]
    related_clause_ids: tuple[str, ...]
    pinned_text_sha256: dict
    conditions: tuple[Condition, ...]
    exceptions: tuple[Exception_, ...]
    non_visual: tuple[str, ...]
    trigger_predicates: tuple[str, ...]
    anchor_policy: str
    review: Review
    condition_map: dict = None   # item_id -> {role} | {all|any: [{predicate, polarity}]}

    def condition_ids(self):
        return [c.id for c in self.conditions]

    def exception_ids(self):
        return [e.id for e in self.exceptions]


@dataclass
class Assessment:
    rule_id: str
    l2: str                        # matched | refuted | not_applicable | insufficient
    policy: str
    states: dict
    refuted_by: list[str] = field(default_factory=list)
    exception_hits: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
