"""Portable packaged resources, with compatibility for the original research checkout."""
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
RESOURCES = PACKAGE / 'resources'
CORE_DIR = RESOURCES / 'core' if (RESOURCES / 'core').is_dir() else ROOT / 'experiments' / 'legal_context'
CORPUS_DIR = RESOURCES / 'corpora' if (RESOURCES / 'corpora').is_dir() else ROOT / 'data'
TOKENIZER_DIR = RESOURCES / 'tokenizer' if (RESOURCES / 'tokenizer').is_dir() else CORE_DIR / 'tokenizer'
