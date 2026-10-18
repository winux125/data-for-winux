"""Exact clause-level view of the verified legal bundle; no paraphrase and no network.

The package's brief loader verifies every snapshot and
section hash. This module only splits those verified lines into clauses, keeps
official notes and footnotes with the clause they describe, and extracts
definitions and act aliases. Every clause text equals its source lines exactly.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .text import stem_tokens
from .types import Act, ActAlias, Amendment, Clause, Definition, SubItem
from .brief import Brief
from .paths import CORE_DIR

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = CORE_DIR / 'section_briefs.json'

CLAUSE_START = re.compile(r'^(\d+(?:-\d+)?)\.\s')
HEADING = re.compile(r'^(?:Глава|Параграф)\s+\d')
SUBITEM = re.compile(r'^(\d+(?:-\d+)?)\)\s')
FOOTNOTE = re.compile(r'^Сноска\.')
OFFICIAL_NOTE = 'Примечание ИЗПИ'
SUSPENSION = re.compile(r'^Действие\s+(пункта|подпункта)\s+(\d+(?:-\d+)?\)?)\s+приостановлено\s+до\s+'
                        r'(\d{2})\.(\d{2})\.(\d{4})')
REPEALED = re.compile(r'^\d+(?:-\d+)?\.\s+Исключ')
DEFINITIONS = re.compile(r'используются\s+следующие\s+(?:основные\s+)?понятия')
DEFINED_TERM = re.compile(r'^\d+(?:-\d+)?\)\s+(.+?),?\s+[–—-]\s+')
AMENDING = re.compile(r'от\s+(\d{2})\.(\d{2})\.(\d{4})\s+№\s*(\d+)\s*(?:\(([^)]*)\))?')
EFFECTIVE_FROM = re.compile(r'вводится\s+в\s+действие\s+с\s+(\d{2})\.(\d{2})\.(\d{4})')
ALIAS = re.compile(r'\(далее\s*[–—-]\s*([^()]{1,160})\)')
REGISTRY = re.compile(r'(?:под\s+(?:номером\s+)?)?№\s*(\d{4,6})')
MONTHS = {m: i + 1 for i, m in enumerate(('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
                                         'августа', 'сентября', 'октября', 'ноября', 'декабря'))}


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_brief(bundle_path=None):
    return Brief(bundle_path or DEFAULT_BUNDLE)


def _iso(day, month, year):
    return f'{int(year):04d}-{int(month):02d}-{int(day):02d}'


def registry_number(source_id):
    """Adilet IDs encode the state registration number: V1900019680 -> 19680."""
    if not re.fullmatch(r'V\d{10}', source_id):
        raise ValueError('Unexpected Adilet source ID: ' + source_id)
    return str(int(source_id[3:]))


def parse_amendments(line_no, text):
    low = text.lower()
    suspension = SUSPENSION.match(text)
    if suspension:
        found = list(AMENDING.finditer(text))
        return [Amendment(kind='suspended', line=line_no, raw=text,
                          act_date=_iso(*found[0].groups()[:3]) if found else None,
                          act_number=found[0].group(4) if found else None,
                          suspended_until=_iso(*suspension.groups()[2:]),
                          target=f'{suspension.group(1)} {suspension.group(2)}')]
    kind = ('excluded' if 'исключ' in low else 'added' if 'дополнен' in low else
            'redaction' if 'в редакции' in low else 'changes' if 'изменени' in low else 'other')
    result = []
    for match in AMENDING.finditer(text):
        note = match.group(5)
        effective = EFFECTIVE_FROM.search(note or '')
        result.append(Amendment(kind=kind, line=line_no, raw=text, act_date=_iso(*match.groups()[:3]),
                                act_number=match.group(4), effective_note=note,
                                effective_from=_iso(*effective.groups()) if effective else None))
    return result or [Amendment(kind=kind, line=line_no, raw=text)]


class Corpus:
    """All main-body clauses of the verified acts, keyed by '{source_id}:{number}'."""

    def __init__(self, brief=None, sources_index=None):
        self.brief = brief or load_brief()
        index_path = Path(sources_index or Path(self.brief.path).with_name('sources.json'))
        titles = {s['source_id']: s for s in json.loads(index_path.read_text(encoding='utf-8'))['sources']}
        self.acts, self.clauses, self.definitions = {}, {}, []
        self.aliases, self.heading_notes, self.orphans, self.preambles = {}, {}, {}, {}
        for source_id, source in self.brief.sources.items():
            entry = titles.get(source_id)
            if not entry or entry['text_sha256'] != source['text_sha256']:
                raise ValueError('sources.json does not describe the verified snapshot: ' + source_id)
            lines = self.brief.body_lines[source_id]
            first = source['main_body_lines_1based'][0]
            self.preambles[source_id] = ((1, first - 1), '\n'.join(lines[:first - 1]) + '\n')
            self.acts[source_id] = Act(
                source_id=source_id, number=source['number'], registry_number=registry_number(source_id),
                title=entry['title'], adopted=self._adopted(lines[:first - 1], source['number']),
                official_url=source['official_url'], text_sha256=source['text_sha256'],
                revision_instant=source['revision_instant'], retrieved_utc=source['retrieved_utc'])
        for source_id in self.brief.sources:
            self._parse(source_id)
            self.aliases[source_id] = self._aliases(source_id)

    @staticmethod
    def _adopted(preamble, number):
        text = '\n'.join(preamble)
        match = re.search(r'от\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})\s+года\s+№\s*' + re.escape(number) + r'\b', text)
        if match and match.group(2) in MONTHS:
            return _iso(match.group(1), MONTHS[match.group(2)], match.group(3))
        return None

    def _section_for(self, source_id, line):
        covering = [s for s in self.brief.sections.values() if s['source_id'] == source_id
                    and s['source_lines_1based'][0] <= line <= s['source_lines_1based'][1]]
        if not covering:
            raise ValueError(f'Clause line {line} of {source_id} is outside verified sections')
        return min(covering, key=lambda s: s['source_lines_1based'][1] - s['source_lines_1based'][0])['section_id']

    def _parse(self, source_id):
        lines = self.brief.body_lines[source_id]
        first, last = self.brief.sources[source_id]['main_body_lines_1based']
        chapter = paragraph = None
        current, pending = None, []
        notes, orphans = [], []
        raw_clauses = []

        def close():
            if current is not None:
                raw_clauses.append(current)

        number = first
        while number <= last:
            text = lines[number - 1]
            if HEADING.match(text):
                close()
                current = None
                if text.startswith('Глава'):
                    chapter, paragraph = text, None
                else:
                    paragraph = text
                number += 1
                continue
            start = CLAUSE_START.match(text)
            if start:
                close()
                current = dict(number=start.group(1), first=number, last=number, notes=pending,
                               headings=tuple(h for h in (chapter, paragraph) if h))
                pending = []
                number += 1
                continue
            following = lines[number] if number < last else ''
            suspension = SUSPENSION.match(following)
            if text.startswith(OFFICIAL_NOTE) and suspension and suspension.group(1) == 'пункта':
                # The note precedes the clause it suspends; it is not part of the previous clause.
                close()
                current = None
                pending = [(number, text), (number + 1, following)]
                number += 2
                continue
            if current is None:
                (notes if FOOTNOTE.match(text) else orphans).append((number, text))
            else:
                current['last'] = number
            number += 1
        close()
        if pending:
            orphans.extend(pending)
        self.heading_notes[source_id] = notes
        self.orphans[source_id] = orphans
        for raw in raw_clauses:
            self._add_clause(source_id, lines, raw)

    def _add_clause(self, source_id, lines, raw):
        clause_id = f"{source_id}:{raw['number']}"
        if clause_id in self.clauses:
            raise ValueError('Duplicate numbered clause: ' + clause_id)
        a, z = raw['first'], raw['last']
        body = lines[a - 1:z]
        text = '\n'.join(body) + '\n'
        amendments, subitems = [], []
        for line_no, note in raw['notes']:
            suspension = SUSPENSION.match(note)
            if suspension:
                if suspension.group(2) != raw['number']:
                    raise ValueError(f'Suspension note for {suspension.group(2)} precedes clause {clause_id}')
                amendments.extend(parse_amendments(line_no, note))
        partial = False
        for offset, line in enumerate(body):
            line_no = a + offset
            if FOOTNOTE.match(line):
                amendments.extend(parse_amendments(line_no, line))
            elif SUSPENSION.match(line):
                amendments.extend(parse_amendments(line_no, line))
                partial = True
            elif SUBITEM.match(line):
                continuation = []
                for later in body[offset + 1:]:
                    if SUBITEM.match(later) or FOOTNOTE.match(later) or later.startswith(OFFICIAL_NOTE):
                        break
                    continuation.append(later)
                subitems.append(SubItem(SUBITEM.match(line).group(1), line_no, '\n'.join([line] + continuation)))
        if REPEALED.match(body[0]):
            amendments.extend(parse_amendments(a, body[0]))
            status = 'repealed'
        elif any(x.kind == 'suspended' and x.target.startswith('пункта') for x in amendments):
            status = 'suspended_wording_uncertain'
        elif partial:
            status = 'partially_suspended_wording_uncertain'
        else:
            status = 'in_force_at_snapshot'
        clause = Clause(clause_id=clause_id, source_id=source_id, number=raw['number'],
                        section_id=self._section_for(source_id, a), headings=raw['headings'], lines=(a, z),
                        text=text, text_sha256=sha256(text), notes=tuple(raw['notes']), subitems=tuple(subitems),
                        amendments=tuple(amendments), status=status)
        self.clauses[clause_id] = clause
        if DEFINITIONS.search(body[0]):
            for item in subitems:
                term = DEFINED_TERM.match(item.text)
                if term:
                    self.definitions.append(Definition(
                        term=term.group(1).strip(), key=tuple(stem_tokens(term.group(1))), clause_id=clause_id,
                        item=item.number, line=item.line, text=item.text))

    def _aliases(self, source_id):
        """'(далее – X)' aliases; an act target only when its registry number precedes the alias."""
        result = []
        by_registry = {act.registry_number: sid for sid, act in self.acts.items()}
        for line_no, line in enumerate(self.brief.body_lines[source_id], 1):
            for match in ALIAS.finditer(line):
                name = match.group(1).strip()
                registered = [m.group(1) for m in REGISTRY.finditer(line[max(0, match.start() - 600):match.start()])]
                if name == 'Правила':
                    target = source_id
                else:
                    target = by_registry.get(registered[-1]) if registered else None
                result.append(ActAlias(name=name, key=tuple(stem_tokens(name)), target_source_id=target,
                                       line=line_no))
        return result

    # Convenience accessors --------------------------------------------------
    def clause(self, clause_id):
        try:
            return self.clauses[clause_id]
        except KeyError:
            raise KeyError('Unknown clause: ' + clause_id) from None

    def by_number(self, source_id, number):
        return self.clauses.get(f'{source_id}:{number}')

    def definitions_in(self, clause_id):
        return [d for d in self.definitions if d.clause_id == clause_id]

    def scope_clause(self, source_id):
        return self.by_number(source_id, '1')

    def manifest(self):
        return dict(bundle_sha256=hashlib.sha256(self.brief.raw).hexdigest(),
                    acts={sid: dict(text_sha256=a.text_sha256, revision_instant=a.revision_instant,
                                    retrieved_utc=a.retrieved_utc) for sid, a in self.acts.items()},
                    clauses=len(self.clauses), definitions=len(self.definitions))
