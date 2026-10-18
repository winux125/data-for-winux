"""Deterministic checks of a call-B explanation, the template fallback, and the final rendering.

The generator writes only sentences. Code checks that every factual claim cites facts with a
decided status, every legal claim cites norm excerpts, the conclusion matches the computed
decision, unknown conditions are named, and no clause number, act number or URL appears.
The citation, URL, frames and timecodes are inserted afterwards by code.
"""
from __future__ import annotations

import re

from .contracts import SENTENCE_KINDS, Sentence
from .describe import ACT_NUMBER, PUNKT, URL, _clock, _date_ru
from .prompts import DECISION_RU

ARTICLE = re.compile(r'(?:\bст\.|стать\w*|глав\w*|раздел\w*|параграф\w*)\s*\d', re.I)
NEGATION = ('не ', 'нет', 'отсутств', 'без ')
UNCERTAIN = ('не установ', 'неизвест', 'не видно', 'не определ', 'не подтвержд', 'не зафикс', 'нет данных', 'не удалось')
GLOBAL_FORBIDDEN = ('исключений нет', 'нет исключений', 'исключения отсутствуют', 'исключений не предусмотрено',
                    'правомерн', 'законн', 'нарушений нет', 'нарушений не выявлено', 'полностью соответств',
                    'соответствует требованиям', 'виновн', 'привлеч', 'наказан', 'штраф')
CLAIMS_VIOLATION = re.compile(r'(?<!не )(?:подтвержда\w*|установлен\w*|доказан\w*|выявлен\w*)\s+(?:\w+\s+)?'
                              r'(?:нарушени|несоответстви)|\bнарушил|является нарушением|допустил\w*\s+нарушени', re.I)
CONCLUSION_CUES = {
    'violation_supported': (('подтвержда',), ('не подтвержд', 'не установ', 'опроверга')),
    'refuted': (('не подтвержд', 'опроверга'), ()),
    'exception_applies': (('исключени', 'допуска'), ()),
    'insufficient': (('не подтвержд', 'не установ'), ()),
    'not_applicable_scope': (('не относится', 'не применя', 'не распространя'), ()),
}
PROHIBITION_WORDS = ('не ', 'запрещ', 'нельзя')
MAX_SENTENCES = 9


def fact_clocks(fact):
    return [_clock(t) for t in (fact.anchor_sec, fact.t_start, fact.t_end) if t is not None]


def validate_explanation(raw, ctx, bundle):
    """Return (sentences, errors). `ctx` is the explanation context built by the pipeline."""
    if not isinstance(raw, dict) or set(raw) != {'sentences'} or not isinstance(raw['sentences'], list):
        return [], ['answer must be {"sentences": [...]}']
    decision = ctx['decision']
    items = {i['item_id']: i for i in ctx['items']}
    spans = set(ctx['spans']) | set(items)
    facts = {f.fact_id: f for f in bundle.facts}
    errors, sentences = [], []
    if not 1 <= len(raw['sentences']) <= MAX_SENTENCES:
        errors.append(f'between 1 and {MAX_SENTENCES} sentences expected')
    for n, s in enumerate(raw['sentences']):
        where = f'sentence {n + 1}'
        if not isinstance(s, dict) or set(s) != {'kind', 'text', 'fact_ids', 'span_ids'}:
            errors.append(f'{where}: keys must be kind, text, fact_ids, span_ids')
            continue
        kind, text = s['kind'], s['text'] if isinstance(s['text'], str) else ''
        if any(not isinstance(s[key], list) or any(not isinstance(v, str) for v in s[key])
               for key in ('fact_ids', 'span_ids')):
            errors.append(f'{where}: fact_ids and span_ids must be lists of strings')
            continue
        fact_ids, span_ids = s['fact_ids'], s['span_ids']
        lowered = text.lower()
        if kind not in SENTENCE_KINDS or not text.strip() or len(text) > 400:
            errors.append(f'{where}: kind must be one of {SENTENCE_KINDS} with non-empty text up to 400 characters')
            continue
        if set(fact_ids) - set(facts) - {o.observation_id for o in bundle.free_observations}:
            errors.append(f'{where}: unknown fact IDs {sorted(set(fact_ids) - set(facts))}')
            continue
        if set(span_ids) - spans:
            errors.append(f'{where}: unknown span IDs {sorted(set(span_ids) - spans)}')
            continue
        if PUNKT.search(text) or ACT_NUMBER.search(text) or URL.search(text) or ARTICLE.search(text):
            errors.append(f'{where}: clause/article/act numbers and URLs are inserted by code, remove them')
        for phrase in GLOBAL_FORBIDDEN:
            if phrase in lowered:
                errors.append(f'{where}: forbidden phrase "{phrase}"')
        if decision != 'violation_supported' and CLAIMS_VIOLATION.search(text):
            errors.append(f'{where}: claims a violation, but the decision is {decision}')
        cited = [facts[i] for i in fact_ids if i in facts]
        if kind == 'observation':
            if not cited:
                errors.append(f'{where}: an observation must cite facts')
            if any(f.status == 'unknown' for f in cited):
                errors.append(f'{where}: an observation may cite only confirmed or refuted facts')
            clocks = [c for f in cited for c in fact_clocks(f)]
            if clocks and not any(c in text for c in clocks):
                errors.append(f'{where}: state the time of the cited fact ({", ".join(sorted(set(clocks)))})')
        if any(f.status == 'refuted' for f in cited) and kind in ('observation', 'mapping') \
                and not any(neg in lowered for neg in NEGATION):
            errors.append(f'{where}: a refuted fact is an observed absence and must be written with a negation')
        if any(f.status == 'unknown' for f in cited) and not any(u in lowered for u in UNCERTAIN):
            errors.append(f'{where}: an unknown fact must be written as not established')
        if kind in ('requirement', 'interpretation') and not span_ids:
            errors.append(f'{where}: a legal claim must cite norm span IDs')
        if kind == 'requirement' and ctx['modality'] == 'prohibition' and not any(w in lowered for w in PROHIBITION_WORDS):
            errors.append(f'{where}: the norm is a prohibition; keep the prohibition wording')
        if kind == 'requirement' and ctx['modality'] == 'obligation' and ('запрещ' in lowered):
            errors.append(f'{where}: the norm is an obligation, not a prohibition')
        if kind == 'mapping' and not fact_ids and not span_ids:
            errors.append(f'{where}: a mapping must cite facts or conditions')
        sentences.append(Sentence(f's{n + 1}', kind, text.strip(), tuple(fact_ids), tuple(span_ids)))
    conclusions = [s for s in sentences if s.kind == 'conclusion']
    if len(conclusions) != 1:
        errors.append('exactly one conclusion sentence is required')
    else:
        required, forbidden = CONCLUSION_CUES[decision]
        text = conclusions[0].text.lower()
        if not any(c in text for c in required) or any(c in text for c in forbidden):
            errors.append(f'the conclusion must state: {DECISION_RU[decision]}')
    if not any(s.kind == 'observation' for s in sentences) and ctx['decided_fact_ids']:
        errors.append('at least one observation sentence is required')
    if not any(s.kind == 'requirement' for s in sentences):
        errors.append('at least one requirement sentence with a norm span is required')
    open_items = [i for i in ctx['items'] if i['state'] == 'unknown' and decision in ('insufficient', 'violation_supported')]
    named = {sid for s in sentences if s.kind == 'limitation' for sid in s.quote_span_ids}
    missing = [i['item_id'] for i in open_items if i['item_id'] not in named]
    if missing:
        errors.append(f'limitation sentences must name every unknown condition: {missing}')
    if decision == 'exception_applies':
        true_exceptions = {i['item_id'] for i in ctx['items'] if i['kind'] == 'exception' and i['state'] == 'true'}
        if not true_exceptions & {sid for s in sentences for sid in s.quote_span_ids}:
            errors.append('cite the applicable exception span')
    return sentences, errors


STATE_RU = {'true': 'выполнено', 'false': 'не выполнено', 'unknown': 'не установлено'}


def template_sentences(ctx, bundle):
    """Mechanical explanation built only from facts, item texts and the decision."""
    sentences, n = [], 0

    def add(kind, text, fact_ids=(), span_ids=()):
        nonlocal n
        n += 1
        sentences.append(Sentence(f's{n}', kind, text, tuple(fact_ids), tuple(span_ids)))

    cited = [bundle.fact(i) for i in ctx['decided_fact_ids']]
    for fact in sorted(cited, key=lambda f: (f.t_start is None, f.t_start or 0)):
        clocks = fact_clocks(fact)
        when = f'В {clocks[0]}' if clocks else 'По переданным данным'
        if fact.status == 'confirmed':
            add('observation', f'{when}: {fact.statement}.', [fact.fact_id])
        else:
            add('observation', f'{when}: не наблюдалось — {fact.statement}.', [fact.fact_id])
    add('requirement', f'Требование нормы: {ctx["requirement"]}', span_ids=list(ctx['spans'])[:1])
    for item in ctx['items']:
        if item['state'] != 'unknown':
            add('mapping', f'{"Условие" if item["kind"] == "condition" else "Исключение"} «{item["text"]}» — '
                           f'{STATE_RU[item["state"]]} по фактам.', item['fact_ids'], [item['item_id']])
    unknown = [i for i in ctx['items'] if i['state'] == 'unknown']
    if unknown:
        add('limitation', 'Не установлено по переданным данным: ' + '; '.join(f'«{i["text"]}»' for i in unknown) + '.',
            span_ids=[i['item_id'] for i in unknown])
    add('conclusion', DECISION_RU[ctx['decision']][0].upper() + DECISION_RU[ctx['decision']][1:] + '.')
    return sentences


def render(sentences, citation, evidence, retrieved_dates):
    """Final text: generator/template sentences + code-inserted basis, evidence and caveats."""
    body = ' '.join(s.text.rstrip() if s.text.rstrip().endswith(('.', '!', '?')) else s.text.rstrip() + '.'
                    for s in sentences)
    proof = '; '.join(
        f'{e["fact_id"]} ({e["status"]}' + (f', {e["clock"]}' if e['clock'] else '') + ')'
        + (': ' + ', '.join(e['evidence_refs']) if e['evidence_refs'] else '') for e in evidence)
    tail = [f'Основание: {citation}.']
    if proof:
        tail.append(f'Доказательства: {proof}.')
    if retrieved_dates:
        tail.append(f'Текст нормы по снимку Әділет от {", ".join(_date_ru(d) for d in retrieved_dates)}; '
                    'применимость редакции к дате события не подтверждена.')
    tail.append('Это подсказка для проверяющего, а не юридическое заключение.')
    return body + ' ' + ' '.join(tail)
