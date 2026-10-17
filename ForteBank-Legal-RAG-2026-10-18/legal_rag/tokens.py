"""Token counting with the generator's own tokenizer; an estimate is always labelled as such."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from .paths import TOKENIZER_DIR

ROOT = Path(__file__).resolve().parents[1]
QWEN_TOKENIZER_DIR = TOKENIZER_DIR
# Measured in this project: the 9,493-character legal brief is 3,609 Qwen3-VL tokens (~2.63 chars/token).
ESTIMATED_CHARS_PER_TOKEN = 2.6


class TokenCounter:
    exact = False
    name = 'abstract'

    def count(self, text):
        raise NotImplementedError

    def describe(self):
        return dict(name=self.name, exact=self.exact)


class EstimatedCounter(TokenCounter):
    """Character-based estimate; budgets built on it are marked `token_count_exact=false`."""
    name = 'estimated_chars_per_token'

    def __init__(self, chars_per_token=ESTIMATED_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def count(self, text):
        return int(len(text) / self.chars_per_token) + 1

    def describe(self):
        return dict(name=self.name, exact=False, chars_per_token=self.chars_per_token)


class HFTokenizerCounter(TokenCounter):
    """The pinned Qwen3-VL tokenizer.json via the `tokenizers` library (no network)."""
    exact = True

    def __init__(self, directory=QWEN_TOKENIZER_DIR):
        from tokenizers import Tokenizer
        directory = Path(directory)
        provenance = json.loads((directory / 'provenance.json').read_text(encoding='utf-8'))
        data = (directory / 'tokenizer.json').read_bytes()
        if hashlib.sha256(data).hexdigest() != provenance['sha256']['tokenizer.json']:
            raise ValueError('Tokenizer file differs from its recorded provenance')
        self.tokenizer = Tokenizer.from_str(data.decode('utf-8'))
        self.name = f"{provenance['repository']}@{provenance['revision']}"

    def count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)


class CallableCounter(TokenCounter):
    """Wraps a loaded transformers tokenizer (e.g. the resident generator's)."""
    exact = True

    def __init__(self, tokenizer, name):
        self.tokenizer, self.name = tokenizer, name

    def count(self, text):
        return len(self.tokenizer(text, add_special_tokens=False)['input_ids'])


def default_counter():
    try:
        return HFTokenizerCounter()
    except ImportError:
        return EstimatedCounter()
