"""Russian description for the competition `description` field, built from the card and corpus.

Facts come from the verifier; every legal number, act number and URL comes from the
card and corpus. `assert_citations_allowed` rejects any other citation, including
ones smuggled into the facts.
"""
from __future__ import annotations

import re

PUNKT = re.compile(r'(?:\bп\.|\bпп\.|пункт\w*|подпункт\w*)\s*(\d+(?:-\d+)?)', re.I)
ACT_NUMBER = re.compile(r'№\s*(\d+)')
URL = re.compile(r'https?://[^\s,;)]+')


class CitationError(ValueError):
    pass


def _date_ru(iso):
    return f'{iso[8:10]}.{iso[5:7]}.{iso[:4]}' if iso else None


def short_title(title):
    """'Об утверждении Правил …, …' -> 'Правил …' up to the first comma (genitive, as cited)."""
    text = re.sub(r'^Об утверждении\s+', '', title)
    head = text.split(',')[0].strip()
    return head + ('…' if head != text.strip() else '')


def citation(card, corpus):
    parts, allowed_numbers, allowed_acts, urls = [], set(), set(), set()
    for clause_id in card.clause_ids:
        clause = corpus.clause(clause_id)
        act = corpus.acts[clause.source_id]
        adopted = _date_ru(act.adopted)
        resolution = f'постановление Правления Национального Банка РК № {act.number}' + (
            f' от {adopted}' if adopted else '')
        parts.append(f'п. {clause.number} {short_title(act.title)} ({resolution}), {act.official_url}')
        allowed_numbers.add(clause.number)
        allowed_acts.add(act.number)
        urls.add(act.official_url)
    for clause_id in card.related_clause_ids:
        allowed_numbers.add(corpus.clause(clause_id).number)
    return '; '.join(parts), allowed_numbers, allowed_acts, urls


def assert_citations_allowed(text, allowed_numbers, allowed_acts, allowed_urls):
    bad = [f'п. {n}' for n in PUNKT.findall(text) if n not in allowed_numbers]
    bad += [f'№ {n}' for n in ACT_NUMBER.findall(text) if n not in allowed_acts]
    bad += [u for u in (m.rstrip('.') for m in URL.findall(text)) if u not in allowed_urls]
    if bad:
        raise CitationError('Citations outside the card/corpus: ' + ', '.join(bad))


def _clock(seconds):
    seconds = max(0., float(seconds))
    return f'{int(seconds // 60):02d}:{seconds % 60:04.1f}'


def describe(card, assessment, corpus, *, anchor_sec, facts):
    if assessment.rule_id != card.rule_id:
        raise ValueError('Assessment belongs to another card')
    cited, numbers, acts, urls = citation(card, corpus)
    facts = [f.strip().rstrip('.') for f in facts if f and f.strip()]
    if not facts:
        raise ValueError('A description needs at least one observed fact')
    retrieved = sorted({_date_ru(corpus.acts[c.split(':')[0]].retrieved_utc[:10]) for c in card.clause_ids})
    lines = [f'{_clock(anchor_sec)} — {card.type_label_ru}. Видно: ' + '; '.join(facts) + '.',
             f'Возможное несоответствие: {cited}.',
             f'Текст нормы по снимку Әділет от {", ".join(retrieved)}; применимость редакции к дате записи не подтверждена.']
    if assessment.caveats:
        questions = {c.id: c.question_ru for c in card.conditions}
        lines.append('Не удалось подтвердить по кадрам: ' + ' '.join(questions[c] for c in assessment.caveats))
    if card.non_visual:
        lines.append('Требует проверки человеком: ' + '; '.join(card.non_visual) + '.')
    lines.append('Это подсказка для проверяющего, а не юридическое заключение.')
    text = ' '.join(lines)
    assert_citations_allowed(text, numbers, acts, urls)
    return text
