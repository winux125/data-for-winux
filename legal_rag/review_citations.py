"""Recognize only citations bound to the selected source; retain other numbers."""
import re

NUMBER = r'\d+(?:[.-]\d+)*'
URL = re.compile(r'https?://[^\s<>«»"\u201c\u201d]+', re.I)


def citation_binding(node_id, norm=None, act_number=None, related=()):
    norm = norm or {}
    kind, number = None, None
    if norm.get('citation_level') != 'document':
        match = re.search(r':([pa])(' + NUMBER + r')$', node_id)
        if match:
            kind, number = ('article' if match[1] == 'a' else 'clause'), match[2]
        else:
            label = norm.get('unit_label') or ''
            match = re.fullmatch(r'(Пункт|Статья)\s+(' + NUMBER + r')\.?', label, re.I)
            if match:kind, number = ('article' if match[1].lower() == 'статья' else 'clause'), match[2]
    related_numbers = []
    if kind and norm.get('source_id'):
        for item in related:
            if item.get('source_id') != norm['source_id']:continue
            if item.get('node_id','').rsplit(':',1)[0] != node_id.rsplit(':',1)[0]:continue
            match = re.search(r':([pa])(' + NUMBER + r')$',item.get('node_id',''))
            if match and ('article' if match[1]=='a' else 'clause')==kind and match[2]!=number:
                related_numbers.append(match[2])
    return {'kind':kind, 'number':number, 'related_numbers':sorted(set(related_numbers)),
            'act_number':str(act_number) if act_number else None,
            'official_url':norm.get('official_url')}


def without_bound_citations(text, binding):
    """Used for validation only. Never erase an unknown source or fact quantity."""
    allowed_url = binding.get('official_url')
    def strip_url(match):
        raw = match[0];candidate = raw.rstrip('.,;:!?)\u005d')
        return raw[len(candidate):] if allowed_url and candidate == allowed_url else raw
    checked = URL.sub(strip_url, text)
    kinds = {
        'clause':r'(?:пункт(?:а|у|е|ом)?|п\.)',
        'article':r'(?:стать(?:я|и|е|ю|ей)|ст\.)',
    }
    if binding.get('kind') in kinds and binding.get('number'):
        allowed = {binding['number'],*binding.get('related_numbers',[])}
        # Lists must be explicitly plural; never swallow a quantity after a
        # singular reference such as "пункт 19, 12 банкнот".
        if binding['kind']=='clause':
            list_pattern = (r'\bпункт(?:ы|ов|ам|ами|ах)\s+('
                            + NUMBER + r'(?:\s*(?:,\s*(?:и\s+)?|и\s+|или\s+)'+NUMBER+r')+)(?![\w-]|\.\d)')
            checked = re.sub(list_pattern,lambda m:'' if set(re.findall(NUMBER,m[1]))<=allowed else m[0],checked,flags=re.I)
        pattern = r'\b' + kinds[binding['kind']] + r'\s*(?:№\s*)?(' + NUMBER + r')(?![\w-]|\.\d)'
        checked = re.sub(pattern,lambda m:'' if m[1] in allowed else m[0],checked,flags=re.I)
    if binding.get('act_number'):
        checked = re.sub(r'№\s*(' + NUMBER + r')(?![\w-]|\.\d)',
            lambda m:'' if m[1] == binding['act_number'] else m[0],checked)
    return checked
