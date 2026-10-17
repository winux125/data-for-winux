"""Local Legal RAG CLI: analyze JSON observations, embed, bench, search and inspect norms."""
import argparse
from dataclasses import asdict
from dataclasses import replace
import json
from pathlib import Path
import sys

from .api import LegalRAG

DEFAULT_QUERIES = Path(__file__).resolve().parent / 'data' / 'eval_queries.json'


def emit(value):
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False, indent=2))


def evaluate(rag, path, k_values=(1, 3, 5), depth=10):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    queries = data['queries']
    for q in queries:
        unknown = [g for g in q['gold'] if g not in rag.corpus.clauses]
        if unknown:
            raise ValueError(f"{q['id']}: unknown gold clauses {unknown}")
    report = dict(status=data.get('status'), author=data.get('author'), queries=len(queries), variants={})
    for name, lexicon in (('bm25', False), ('bm25_lexicon', True)):
        ranks, negatives = [], []
        for q in queries:
            hits = rag.search(q['text'], k=depth, lexicon=lexicon)
            if not q['gold']:
                negatives.append(dict(id=q['id'], top=hits[0].clause_id if hits else None,
                                      top_score=hits[0].score if hits else 0.))
                continue
            rank = next((h.rank for h in hits if h.clause_id in q['gold']), None)
            ranks.append(dict(id=q['id'], kind=q['kind'], rank=rank))
        n = len(ranks)
        summary = {f'recall@{k}': round(sum(1 for r in ranks if r['rank'] and r['rank'] <= k) / n, 3) for k in k_values}
        summary['mrr@10'] = round(sum(1 / r['rank'] for r in ranks if r['rank']) / n, 3)
        summary['misses@10'] = [r['id'] for r in ranks if not r['rank']]
        summary['per_query'] = ranks
        summary['negatives'] = negatives
        report['variants'][name] = summary
    return report


def main():
    parser = argparse.ArgumentParser(prog='python -m legal_rag', description=__doc__)
    parser.add_argument('--source-library',type=Path,help='Explicit versioned manifest for document-level retrieval')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('search')
    s.add_argument('text')
    s.add_argument('--k', type=int, default=5)
    s.add_argument('--pred', nargs='*', default=[])
    s.add_argument('--no-lexicon', action='store_true')
    p = sub.add_parser('packet')
    p.add_argument('--rule', nargs='*', default=[])
    p.add_argument('--clause', nargs='*', default=[])
    p.add_argument('--query', nargs='*', default=[])
    p.add_argument('--pred', nargs='*', default=[])
    p.add_argument('--budget', type=int, default=24000)
    p.add_argument('--full', action='store_true', help='print exact texts, not only the item summary')
    sub.add_parser('cards')
    e = sub.add_parser('eval')
    e.add_argument('--queries', default=str(DEFAULT_QUERIES))
    sub.add_parser('manifest')
    s2=sub.add_parser('source-search',help='Expanded official library with document-level citations')
    s2.add_argument('text');s2.add_argument('--k',type=int,default=5)
    s2.add_argument('--include-context',action='store_true');s2.add_argument('--include-guidance',action='store_true')
    s2.add_argument('--include-historical',action='store_true')
    sp=sub.add_parser('source-packet');sp.add_argument('chunks',nargs='+');sp.add_argument('--budget-tokens',type=int,default=4000)
    sub.add_parser('source-manifest')
    for name in ('analyze', 'embed', 'bench', 'doctor'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--config', type=Path)
        cmd.add_argument('--device', help='Explicit cpu or cuda:N override')
        cmd.add_argument('--output', type=Path)
        if name in ('analyze', 'bench'):
            cmd.add_argument('--index-dir', type=Path)
            cmd.add_argument('--retrieval', choices=('bm25', 'dense', 'hybrid'))
            cmd.add_argument('--top-k', type=int)
        if name == 'analyze':
            cmd.add_argument('--input', required=True, type=Path)
            cmd.add_argument('--template-only', action='store_true', help='Explicit CPU wiring; no Qwen claims')
        if name == 'embed':
            cmd.add_argument('--test-embedder', action='store_true', help='Hash vectors for tests, not semantic retrieval')
        if name == 'bench':
            cmd.add_argument('--run-models', action='store_true', help='Use local real models and the prebuilt index')
    args = parser.parse_args()
    if args.command in ('analyze', 'embed', 'bench', 'doctor'):
        from .config import load_config
        config = load_config(args.config) if args.config else load_config()
        if args.device:
            config = config.with_device(args.device)
        if getattr(args, 'retrieval', None):
            config = replace(config, retrieval=replace(config.retrieval, mode=args.retrieval))
        if getattr(args, 'top_k', None) is not None:
            config = replace(config, retrieval=replace(config.retrieval, top_k=args.top_k))
        config.validate()
        if args.command == 'doctor':
            from .resources import environment
            value = dict(environment=environment(), config=config.to_dict())
        else:
            rag = LegalRAG(source_library_path=args.source_library)
            if args.command == 'analyze':
                raw = json.loads(args.input.read_text(encoding='utf-8-sig'))
                value = rag.analyze(raw, config, template_only=args.template_only, index_dir=args.index_dir).to_dict()
            elif args.command == 'embed':
                from .embed import DEFAULT_INDEX_DIR, HashEmbedder, build_index, make_embedder
                if args.test_embedder and args.output is None:
                    raise ValueError('--test-embedder requires an explicit --output directory')
                if not args.test_embedder and config.embedder.device.startswith('cuda'):
                    from .resources import cuda_preflight
                    cuda_preflight(config)
                embedder = HashEmbedder() if args.test_embedder else make_embedder(config.embedder)
                value = build_index(rag.source_library(), embedder, args.output or DEFAULT_INDEX_DIR)
            else:
                from .bench import run
                value = run(rag, config, models=args.run_models, index_dir=args.index_dir)
        if args.output and args.command != 'embed':
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
            emit(dict(output=str(args.output.resolve())))
        else:
            emit(value)
        return
    rag = LegalRAG(source_library_path=args.source_library)
    if args.command == 'search':
        hits = rag.search(args.text, k=args.k, predicates=args.pred, lexicon=not args.no_lexicon)
        emit([dict(asdict(h), headings=rag.corpus.clause(h.clause_id).headings,
                   text=rag.corpus.clause(h.clause_id).text[:400]) for h in hits])
    elif args.command == 'packet':
        packet = rag.packet(rule_ids=args.rule, clause_ids=args.clause, query_texts=args.query,
                            predicates=args.pred, budget_chars=args.budget)
        if args.full:
            emit(packet.to_dict())
        else:
            emit(dict(items=[dict(tier=i.tier, kind=i.kind, clause_id=i.clause_id, status=i.status, reason=i.reason,
                                  chars=len(i.text)) for i in packet.items],
                      omitted=packet.omitted, unresolved=packet.unresolved, coverage=packet.coverage,
                      needs_review=packet.needs_review, serialized_chars=packet.serialized_chars))
    elif args.command == 'cards':
        emit(dict(meta=rag.cards_meta, cards=[dict(rule_id=c.rule_id, type=c.type_label_ru, kind=c.kind,
                                                   clauses=c.clause_ids, human_reviewed=c.review.human_reviewed,
                                                   production_active=c.review.production_active)
                                              for c in rag.cards.values()]))
    elif args.command == 'eval':
        emit(evaluate(rag, args.queries))
    elif args.command == 'source-search':
        emit(rag.search_sources(args.text,k=args.k,include_context=args.include_context,
            include_guidance=args.include_guidance,include_historical=args.include_historical))
    elif args.command == 'source-packet':emit(rag.packet_sources(args.chunks,budget_tokens=args.budget_tokens))
    elif args.command == 'source-manifest':emit(rag.source_library().summary())
    else:
        emit(rag.manifest())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, ImportError, OSError) as error:
        print(json.dumps(dict(error=type(error).__name__, message=str(error)), ensure_ascii=True), file=sys.stderr)
        sys.exit(1)
