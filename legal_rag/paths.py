"""Canonical checked-in resources; missing assets never select a legacy corpus."""
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
RESOURCES = PACKAGE / 'resources'
CORE_DIR = RESOURCES / 'core'
CORPUS_DIR = RESOURCES / 'corpora'
TOKENIZER_DIR = RESOURCES / 'tokenizer'
