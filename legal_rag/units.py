"""Structural normative units (parent) and search chunks (child) for the source library.

Documents are split by type, not by one `N.` regex over the whole text: numbers repeat
in the resolution, the approved document, articles and appendices. Every source line
belongs to exactly one unit; a unit's text is its exact source lines. Footnotes and
official suspension notes stay inside their unit's range but are excluded from search
text. When numbering in a container is not monotonic and unique, the container falls
back to exact line ranges with document-level citation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import re

from .corpus import FOOTNOTE, OFFICIAL_NOTE, SUSPENSION, parse_amendments
from .refs import REF

PARSER_VERSION = 'units-v2'
CHILD_MAX_CHARS = 1200      # search text of a child; short parents are never split
LEAD_MAX_CHARS = 400        # introductory wording repeated in each child of a large parent
FALLBACK_CHARS = 3000

CLAUSE = re.compile(r'^(\d+(?:-\d+)?)\.\s')
SUBITEM = re.compile(r'^(\d+(?:-\d+)?)\)\s')
# Case-insensitive, Arabic or Roman numbering ('РАЗДЕЛ 1.', 'Раздел I.'); a number is required, so
# 'Глава представительства ...' is body text, not a heading.
HEADING = re.compile(r'^(?:раздел|подраздел|глава|параграф)\s+(?:\d+(?:-\d+)?|[IVXLC]+)(?=[.\s]|$)', re.I)
HEADING_DEPTH = {'раздел': 0, 'подраздел': 1, 'глава': 2, 'параграф': 3}
ARTICLE_REF = re.compile(r'(?<![а-яё])стать(?:я|и|е|ю|ей|ям|ях|ями)\s+(\d+(?:-\d+)?(?:\s*(?:,|и)\s*\d+(?:-\d+)?)*)', re.I)
ARTICLE = re.compile(r'^Статья\s+(\d+(?:-\d+)?)\.')
APPROVED = re.compile(r'^(?:Утвержден[аоы]?|УТВЕРЖДЕН[АОЫ]?)\b')
ATTACHMENT = re.compile(r'^Приложение(?:\s+(\d+(?:-\d+)?))?\s*(?:к\s+(.*))?$')
RESOLUTION_TARGET = re.compile(r'^к\s+(?:постановлени|приказ|совместн|решени|распоряжени|указ)', re.I)
REPEALED = re.compile(r'^(?:\d+(?:-\d+)?\.|Статья\s+\d+(?:-\d+)?\.)\s*Исключен', re.I)
DEFINITIONS = re.compile(r'используются\s+следующие\s+(?:основные\s+)?понятия')
EXCEPTION_CUES = ('за исключением', 'кроме', 'не распространяется', 'допускается', 'не допускается',
                  'запрещается', 'в случае', 'при условии')
LAW_MIN_ARTICLES = 3


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _number_key(number):
    head, _, tail = number.partition('-')
    return int(head), int(tail or 0)


def _is_note(line):
    return bool(FOOTNOTE.match(line) or line.startswith(OFFICIAL_NOTE) or SUSPENSION.match(line))


def _suspends_whole_provision(line):
    """'Действие пункта N приостановлено' precedes the clause it suspends; 'подпункта' stays inside."""
    match = SUSPENSION.match(line)
    return bool(match and match.group(1) == 'пункта')


@dataclass
class Unit:
    unit_id: str
    source_id: str
    container: str              # resolution | rulesN | appendixN | law | material
    kind: str                   # clause | article | resolution_clause | header | heading | preamble | material | span
    number: str | None
    lines: tuple[int, int]      # full exact range, including preceding official notes
    body_start: int             # first line of the provision itself
    headings: tuple[str, ...]
    text: str
    text_sha256: str
    search_text: str
    status: str
    structure: str              # structured | fallback
    citation_level: str         # unit | document
    label: str | None           # 'п. 22', 'ст. 15', None for fallback/header units
    amendments: list = field(default_factory=list)
    exception_cues: list = field(default_factory=list)
    definitions: list = field(default_factory=list)
    references: list = field(default_factory=list)
    parts: dict = field(default_factory=dict)   # numbered parts 'N.' of an article: number -> [first, last]
    indexed: bool = True
    numbering_anomaly: str | None = None
    parent_id: str | None = None
    structural_path: list = field(default_factory=list)


@dataclass
class Chunk:
    chunk_id: str
    unit_id: str
    source_id: str
    part: int
    lines: tuple[int, int]
    text: str                   # exact source lines of this child
    text_sha256: str
    search_text: str            # lead wording + normative lines, no notes
    search_sha256: str
    parent_sha256: str


@dataclass
class DocumentStructure:
    source_id: str
    parser_version: str
    containers: list
    units: list
    chunks: list
    fallback_reasons: dict

    def summary(self):
        return dict(source_id=self.source_id, parser_version=self.parser_version,
                    containers=[(c['name'], c['lines'], c['structure']) for c in self.containers],
                    units=len(self.units), chunks=len(self.chunks), fallback_reasons=self.fallback_reasons)


def _containers(lines, role):
    """[(name, first, last)] 1-based inclusive ranges that partition the document."""
    n = len(lines)
    if role == 'guidance':
        return [('material', 1, n)]
    if sum(1 for line in lines if ARTICLE.match(line)) >= LAW_MIN_ARTICLES:
        return [('law', 1, n)]
    starts = []
    rules = appendices = 0
    for i, line in enumerate(lines):
        if APPROVED.match(line):
            rules += 1
            starts.append((i + 1, f'rules{rules}'))
            continue
        match = ATTACHMENT.match(line)
        if match:
            target = match.group(2) or (lines[i + 1] if i + 1 < n else '')
            if RESOLUTION_TARGET.match('к ' + target if match.group(2) else target):
                # The approved document itself is formatted as an attachment to the resolution.
                if starts and starts[-1][0] >= i - 3 and starts[-1][1].startswith('rules'):
                    continue  # stamp already opened this approved document
                rules += 1
                starts.append((i + 1, f'rules{rules}'))
            elif target.startswith('к ') or match.group(1):
                appendices += 1
                starts.append((i + 1, f'appendix{appendices}'))
    result, previous = [], 1
    name = 'resolution'
    for first, next_name in starts:
        if first > previous:
            result.append((name, previous, first - 1))
        name, previous = next_name, first
    result.append((name, previous, n))
    return result


def _notes_and_amendments(lines, first, last):
    amendments = []
    for number in range(first, last + 1):
        line = lines[number - 1]
        if FOOTNOTE.match(line) or SUSPENSION.match(line) or REPEALED.match(line):
            amendments.extend(asdict(a) for a in parse_amendments(number, line))
    return amendments


def _status(lines, body_start, last, amendments):
    if REPEALED.match(lines[body_start - 1]):
        return 'repealed'
    suspended = [a for a in amendments if a['kind'] == 'suspended']
    if any(a['target'] and a['target'].startswith('пункта') for a in suspended):
        return 'suspended_wording_uncertain'
    if suspended:
        return 'partially_suspended_wording_uncertain'
    return 'in_force_at_snapshot'


class _Builder:
    def __init__(self, source_id, lines):
        self.source_id, self.lines = source_id, lines
        self.units, self.used_ids = [], set()

    def _unique(self, unit_id):
        candidate, k = unit_id, 2
        while candidate in self.used_ids:
            candidate, k = f'{unit_id}~{k}', k + 1
        self.used_ids.add(candidate)
        return candidate

    def add(self, container, kind, number, first, last, body_start, headings, structure, label, indexed=True):
        text = '\n'.join(self.lines[first - 1:last]) + '\n'
        normative = [self.lines[i - 1] for i in range(body_start, last + 1) if not _is_note(self.lines[i - 1])]
        search = '\n'.join(list(headings[-2:]) + normative)
        amendments = _notes_and_amendments(self.lines, first, last)
        low = '\n'.join(normative).lower()
        suffix = {'clause': f'p{number}', 'article': f'art{number}', 'resolution_clause': f'r{number}'}.get(
            kind, f'{kind}:{first}-{last}')
        unit = Unit(unit_id=self._unique(f'{self.source_id}:{container}:{suffix}'), source_id=self.source_id,
                    container=container, kind=kind, number=number, lines=(first, last), body_start=body_start,
                    headings=tuple(headings), text=text, text_sha256=sha256(text), search_text=search,
                    status=_status(self.lines, body_start, last, amendments) if kind in ('clause', 'article') else
                    'in_force_at_snapshot', structure=structure,
                    citation_level='unit' if label else 'document', label=label, amendments=amendments,
                    exception_cues=[c for c in EXCEPTION_CUES if c in low], indexed=indexed)
        self.units.append(unit)
        return unit


def _spans(lines, first, last, budget=FALLBACK_CHARS):
    """Non-overlapping exact line ranges; a long line is never cut."""
    start = first
    while start <= last:
        end, size = start, 0
        while end <= last and (end == start or size + len(lines[end - 1]) + 1 <= budget):
            size += len(lines[end - 1]) + 1
            end += 1
        yield start, end - 1
        start = end


def _numbered(lines, first, last, pattern):
    """Provisions of a container and a structure check.

    Numbers must be unique. Isolated order breaks (e.g. a misprinted number inside an
    otherwise continuous sequence) are tolerated up to one per 200 provisions and are
    reported per line; anything more means the structure is not reliably recognized.
    """
    found = [(i, pattern.match(lines[i - 1]).group(1)) for i in range(first, last + 1) if pattern.match(lines[i - 1])]
    numbers = [n for _, n in found]
    keys = [_number_key(n) for n in numbers]
    counts = {n: numbers.count(n) for n in set(numbers)}
    misprints, breaks = set(), 0
    for j in range(len(keys) - 1):
        if keys[j + 1] <= keys[j]:
            breaks += 1
            # A misprint both breaks the order and duplicates a later number: flag the duplicated line.
            misprints.add(found[j][0] if counts[numbers[j]] > 1 else found[j + 1][0])
    duplicates_explained = all(any(i in misprints for i, m in found if m == n) for n, c in counts.items() if c > 1)
    # Small containers get no tolerance; a long one may carry an isolated misprint.
    ok = bool(found) and duplicates_explained and breaks <= len(found) // 200
    return found, ok, misprints


def _structured(builder, name, first, last, pattern, kind, label_fmt, anomalies=frozenset()):
    """Provisions split at numbered starts and headings; notes preceding a clause join it."""
    lines = builder.lines
    headings, pending_from = [], None
    position = first
    starts = {i for i in range(first, last + 1) if pattern.match(lines[i - 1])}
    head_lines = {i for i in range(first, last + 1) if HEADING.match(lines[i - 1])}
    first_provision = min(starts | head_lines, default=last + 1)
    if first_provision > first:
        builder.add(name, 'header' if name.startswith('rules') else 'preamble', None, first, first_provision - 1,
                    first, (), 'structured', None, indexed=name == 'law')
    position = first_provision
    while position <= last:
        line = lines[position - 1]
        if position in head_lines:
            end = position
            while end + 1 <= last and end + 1 not in starts and end + 1 not in head_lines and not (
                    lines[end].startswith(OFFICIAL_NOTE)):
                end += 1
            depth = HEADING_DEPTH[line.split()[0].lower()]
            headings = [h for h in headings if HEADING_DEPTH[h.split()[0].lower()] < depth]
            headings.append(line)
            builder.add(name, 'heading', None, position, end, position, tuple(headings), 'structured', None,
                        indexed=False)
            position = end + 1
            continue
        note_start = position
        if line.startswith(OFFICIAL_NOTE):
            # An official suspension note belongs to the provision that follows it.
            position += 1
            while position <= last and position not in starts and position not in head_lines:
                position += 1
            if position > last or position in head_lines:
                builder.add(name, 'span', None, note_start, position - 1, note_start, tuple(headings), 'structured',
                            None, indexed=False)
                continue
        number = pattern.match(lines[position - 1]).group(1)
        end = position
        while end + 1 <= last and end + 1 not in starts and end + 1 not in head_lines and not (
                lines[end].startswith(OFFICIAL_NOTE) and end + 2 <= last and _suspends_whole_provision(lines[end + 1])):
            end += 1
        unit = builder.add(name, kind, number, note_start, end, position, tuple(headings), 'structured',
                           label_fmt.format(number))
        if position in anomalies:
            unit.numbering_anomaly = 'number out of sequence in the source; cited as printed'
        position = end + 1


def parse_document(source_id, lines, role):
    builder = _Builder(source_id, lines)
    containers, reasons = [], {}
    for name, first, last in _containers(lines, role):
        structure = 'structured'
        if name == 'material':
            builder.add(name, 'material', None, first, last, first, (), 'structured', None)
        elif name == 'law':
            _, ok, anomalies = _numbered(lines, first, last, ARTICLE)
            if ok:
                _structured(builder, name, first, last, ARTICLE, 'article', 'ст. {}', anomalies)
            else:
                structure, reasons[name] = 'fallback', 'article numbering not monotonic/unique'
        elif name == 'resolution' or name.startswith('rules'):
            found, ok, anomalies = _numbered(lines, first, last, CLAUSE)
            if ok:
                kind = 'resolution_clause' if name == 'resolution' else 'clause'
                _structured(builder, name, first, last, CLAUSE, kind, 'п. {}', anomalies)
            else:
                structure = 'fallback'
                reasons[name] = 'no numbered provisions' if not found else 'clause numbering not monotonic/unique'
        else:
            structure = 'fallback'  # appendices: forms and tables with their own numbering
        if structure == 'fallback':
            for a, b in _spans(lines, first, last):
                builder.add(name, 'span', None, a, b, a, (), 'fallback', None)
        containers.append(dict(name=name, lines=(first, last), structure=structure))
    _link(builder.units, lines)
    chunks = [c for unit in builder.units for c in _children(unit, lines)]
    return DocumentStructure(source_id, PARSER_VERSION, containers, builder.units, chunks, reasons)


def _parts(unit, lines):
    """Numbered internal parts ('1.', '2.' ...) of a law article, as exact line ranges."""
    body = [i for i in range(unit.body_start + 1, unit.lines[1] + 1) if not _is_note(lines[i - 1])]
    starts = [(i, CLAUSE.match(lines[i - 1]).group(1)) for i in body if CLAUSE.match(lines[i - 1])]
    parts = {}
    for k, (first, number) in enumerate(starts):
        last = (starts[k + 1][0] - 1) if k + 1 < len(starts) else unit.lines[1]
        parts.setdefault(number, [first, last])
    return parts


def _classify_tail(tail):
    """Which document or node a reference phrase points to, from the words that follow it."""
    tail = tail.lstrip(' ,;:').lower()
    if tail.startswith(('настоящей статьи', 'настоящей статье')):
        return 'this_article'
    if tail.startswith(('настоящего пункта', 'настоящем пункте')):
        return 'this_unit'
    match = re.match(r'стать\w*\s+(\d+(?:-\d+)?)\s+настоящего\s+(?:закона|кодекса)', tail)
    if match:
        return ('law_article', match.group(1))
    if tail.startswith(('настоящих правил', 'настоящего параграфа', 'настоящей главы', 'настоящих требований',
                        'настоящей инструкции', 'настоящего положения')):
        return 'same_container'
    if re.match(r'(?:правил|требований|инструкции)(?:[.,;:)]|\s*$)', tail):
        return 'same_container'   # 'пунктами 57 и 58 Правил.' — the act's own defined short name
    return 'other'


def _link(units, lines):
    """Definitions and references inside one document (cross-act links are resolved by the packer).

    'пункт 3 настоящей статьи' points to part 3 of the SAME article, never to article 3;
    a target that cannot be located stays unresolved with its source preserved.
    """
    by_number = {(u.container, u.number): u for u in units if u.number}
    for unit in units:
        if unit.kind == 'article':
            unit.parts = _parts(unit, lines)
    for unit in units:
        if not unit.indexed:
            continue
        body = [lines[i - 1] for i in range(unit.body_start, unit.lines[1] + 1) if not _is_note(lines[i - 1])]
        if DEFINITIONS.search(' '.join(body)):
            for line in body:
                term = re.match(r'^(\d+(?:-\d+)?)\)\s+(.+?),?\s+[–—-]\s+', line)
                if term:
                    unit.definitions.append(dict(item=term.group(1), term=term.group(2).strip()))
        for line in body:
            for match in REF.finditer(line):
                numbers = re.findall(r'\d+(?:-\d+)?', match.group('nums'))
                if match.group('sub'):
                    # 'подпункт N) пункта M ...' -> clause/part M; 'подпункт N) настоящего пункта' -> this unit.
                    numbers = [match.group('parent')] if match.group('parent') else []
                where = _classify_tail(line[match.end():match.end() + 80])
                for number in numbers or [None]:
                    target = reason = resolution = None
                    if where == 'this_unit' or number is None:
                        target, resolution = unit.unit_id, 'this_unit'
                    elif where == 'this_article':
                        if unit.kind == 'article' and number in unit.parts:
                            target, resolution = f'{unit.unit_id}/part{number}', 'internal_part'
                        else:
                            reason = 'internal_part_not_found'
                    elif isinstance(where, tuple):
                        article = by_number.get(('law', where[1]))
                        if article is not None and number in article.parts:
                            target, resolution = f'{article.unit_id}/part{number}', 'law_article_part'
                        else:
                            reason = 'law_article_part_not_found'
                    elif where == 'same_container':
                        found = by_number.get((unit.container, number))
                        if found is not None:
                            target, resolution = found.unit_id, 'same_container'
                        else:
                            reason = 'not_found_in_container'
                    else:
                        reason = 'other_document_or_unrecognized'
                    unit.references.append(dict(phrase=line[match.start():match.end() + 40], number=number,
                                                target_unit_id=target, resolution=resolution,
                                                unresolved_reason=reason))
            for match in ARTICLE_REF.finditer(line):
                if match.start() == 0 and ARTICLE.match(line):
                    continue  # the article's own title line, not a reference
                tail = line[match.end():match.end() + 60].lstrip(' ,;:').lower()
                own_law = tail.startswith(('настоящего закона', 'настоящего кодекса'))
                for number in re.findall(r'\d+(?:-\d+)?', match.group(1)):
                    found = by_number.get(('law', number)) if own_law else None
                    unit.references.append(dict(phrase=line[match.start():match.end() + 40], number=number,
                                                target_unit_id=found.unit_id if found else None,
                                                resolution='same_law_article' if found else None,
                                                unresolved_reason=None if found else (
                                                    'article_not_found' if own_law else 'other_document_or_unrecognized')))


def _children(unit, lines):
    """Short units are one child; long ones split at subitems/lines, each child keeping the lead."""
    if not unit.indexed:
        body = []
    else:
        body = [i for i in range(unit.body_start, unit.lines[1] + 1) if not _is_note(lines[i - 1])]
    if not unit.indexed or len(unit.search_text) <= CHILD_MAX_CHARS or len(body) < 2:
        return [_chunk(unit, 0, unit.lines, unit.search_text, lines)]
    lead_line = body[0]
    lead = lines[lead_line - 1][:LEAD_MAX_CHARS]
    # Every child repeats headings and the lead; the remaining budget is for its own lines.
    room = max(CHILD_MAX_CHARS // 3, CHILD_MAX_CHARS - len('\n'.join(list(unit.headings[-2:]) + [lead])))
    groups, current, size = [], [], 0
    for i in body[1:]:
        line = lines[i - 1]
        boundary = bool(SUBITEM.match(line) or CLAUSE.match(line))
        if current and (size + len(line) > room or (boundary and size > room // 2)):
            groups.append(current)
            current, size = [], 0
        current.append(i)
        size += len(line) + 1
    if current:
        groups.append(current)
    if len(groups) <= 1:
        return [_chunk(unit, 0, unit.lines, unit.search_text, lines)]
    result = []
    for part, group in enumerate(groups):
        first = unit.lines[0] if part == 0 else group[0]
        last = unit.lines[1] if part == len(groups) - 1 else groups[part + 1][0] - 1
        # The first child carries the full lead line; later children repeat its shortened form.
        own_lead = lines[lead_line - 1] if part == 0 else lead
        search = '\n'.join(list(unit.headings[-2:]) + [own_lead] + [lines[i - 1] for i in group])
        result.append(_chunk(unit, part, (first, last), search, lines))
    return result


def _chunk(unit, part, span, search_text, lines):
    text = '\n'.join(lines[span[0] - 1:span[1]]) + '\n'
    return Chunk(chunk_id=f'{unit.unit_id}#c{part}', unit_id=unit.unit_id, source_id=unit.source_id, part=part,
                 lines=span, text=text, text_sha256=sha256(text), search_text=search_text,
                 search_sha256=sha256(search_text), parent_sha256=unit.text_sha256)
