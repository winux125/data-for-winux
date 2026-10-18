"""Local normative retrieval for the ForteBank cash-desk video service.

Exact clauses of verified Adilet snapshots, reference closure, BM25 search, rule
cards and a fail-closed decision/publication layer. Standard library only.
"""

__all__ = ['LegalRAG', 'shared']


def __getattr__(name):
    if name in __all__:
        from . import api
        return getattr(api, name)
    raise AttributeError(name)
