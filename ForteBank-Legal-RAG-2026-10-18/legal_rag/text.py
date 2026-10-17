"""Russian normalization, stop words and a Snowball Russian stemmer (stdlib only)."""
from functools import lru_cache
import re

TOKEN = re.compile(r'[a-zа-я]+|\d+(?:-\d+)?')
VOWELS = frozenset('аеиоуыэюя')
STOP = frozenset('''
а без более бы был была были было быть в вам вас весь во вот все всего всех вы где да даже для до
его ее ей ему если есть еще же за и из или им их к как ко когда кто ли либо между мне мы на над
не него нее нет ни них но о об однако он она они оно от по под при про с со так также такой там
то того тоже той только том тот у уже чем что чтобы эта эти это этого этой этом этот я
'''.split())


def _endings(*groups):
    """(ending, requires preceding а/я) sorted longest first, as Snowball 'among' matches."""
    pairs = [(e, flag) for words, flag in groups for e in words]
    return sorted(pairs, key=lambda p: -len(p[0]))


PERFECTIVE = _endings((('в', 'вши', 'вшись'), True), (('ив', 'ивши', 'ившись', 'ыв', 'ывши', 'ывшись'), False))
ADJECTIVE = _endings((('ее', 'ие', 'ые', 'ое', 'ими', 'ыми', 'ей', 'ий', 'ый', 'ой', 'ем', 'им', 'ым', 'ом',
                       'его', 'ого', 'ему', 'ому', 'их', 'ых', 'ую', 'юю', 'ая', 'яя', 'ою', 'ею'), False))
PARTICIPLE = _endings((('ем', 'нн', 'вш', 'ющ', 'щ'), True), (('ивш', 'ывш', 'ующ'), False))
REFLEXIVE = _endings((('ся', 'сь'), False))
VERB = _endings((('ла', 'на', 'ете', 'йте', 'ли', 'й', 'л', 'ем', 'н', 'ло', 'но', 'ет', 'ют', 'ны', 'ть', 'ешь',
                  'нно'), True),
                (('ила', 'ыла', 'ена', 'ейте', 'уйте', 'ите', 'или', 'ыли', 'ей', 'уй', 'ил', 'ыл', 'им', 'ым', 'ен',
                  'ило', 'ыло', 'ено', 'ят', 'ует', 'уют', 'ит', 'ыт', 'ены', 'ить', 'ыть', 'ишь', 'ую', 'ю'), False))
NOUN = _endings((('а', 'ев', 'ов', 'ие', 'ье', 'е', 'иями', 'ями', 'ами', 'еи', 'ии', 'и', 'ией', 'ей', 'ой', 'ий',
                  'й', 'иям', 'ям', 'ием', 'ем', 'ам', 'ом', 'о', 'у', 'ах', 'иях', 'ях', 'ы', 'ь', 'ию', 'ью', 'ю',
                  'ия', 'ья', 'я'), False))
SUPERLATIVE = _endings((('ейш', 'ейше'), False))
DERIVATIONAL = _endings((('ост', 'ость'), False))


def _region(word, start):
    for i in range(start + 1, len(word)):
        if word[i - 1] in VOWELS and word[i] not in VOWELS:
            return i + 1
    return len(word)


def _remove(word, limit, endings):
    """Remove the longest matching ending inside [limit:]; None when the among fails."""
    for ending, needs_a_ya in endings:
        cut = len(word) - len(ending)
        if cut >= limit and word.endswith(ending):
            if needs_a_ya and not (cut - 1 >= limit and word[cut - 1] in 'ая'):
                return None
            return word[:cut]
    return None


# Domain forms Snowball splits from their own paradigm (verb-like '-ил', '-ила', '-ило' endings).
EXCEPTIONS = {'правил': 'правил', 'правила': 'правил', 'правило': 'правил'}


# Pure function of the word; the corpus vocabulary is small relative to token count.
@lru_cache(maxsize=None)
def stem(word):
    word = word.lower().replace('ё', 'е')
    if word in EXCEPTIONS:
        return EXCEPTIONS[word]
    rv = next((i + 1 for i, ch in enumerate(word) if ch in VOWELS), len(word))
    r2 = _region(word, _region(word, 0))
    result = _remove(word, rv, PERFECTIVE)
    if result is None:
        word = _remove(word, rv, REFLEXIVE) or word
        result = _remove(word, rv, ADJECTIVE)
        if result is not None:
            result = _remove(result, rv, PARTICIPLE) or result
        else:
            result = _remove(word, rv, VERB)
            if result is None:
                result = _remove(word, rv, NOUN)
    word = result if result is not None else word
    if word.endswith('и') and len(word) - 1 >= rv:
        word = word[:-1]
    derived = _remove(word, max(r2, rv), DERIVATIONAL)
    word = derived if derived is not None else word
    if word.endswith('нн'):
        return word[:-1]
    superlative = _remove(word, rv, SUPERLATIVE)
    if superlative is not None:
        return superlative[:-1] if superlative.endswith('нн') else superlative
    if word.endswith('ь') and len(word) - 1 >= rv:
        return word[:-1]
    return word


def tokens(text):
    return TOKEN.findall(text.lower().replace('ё', 'е'))


def stem_tokens(text, keep_stop=False):
    return [stem(t) if not t[0].isdigit() else t for t in tokens(text) if keep_stop or t not in STOP]
