"""Reproducible development benchmark. Synthetic wiring is never reported as model quality."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .resources import environment
from .retrieve import Retriever

QUERIES = Path(__file__).parent / 'data' / 'eval_queries.json'


def summary(rows):
    positives = [r for r in rows if r['gold']]
    n = len(positives)
    result = dict(positive_queries=n, negative_controls=len(rows) - n)
    for key in ('norm', 'document'):
        ranks = [r[key + '_rank'] for r in positives]
        result[key] = {f'recall@{k}': sum(r is not None and r <= k for r in ranks) / n if n else None
                       for k in (1, 3, 5, 10, 20)}
        result[key]['mrr@20'] = sum(1 / r for r in ranks if r is not None) / n if n else None
    return result


def retrieval_benchmark(rag, queries_path=QUERIES, *, retriever=None, modes=('bm25',)):
    path = Path(queries_path)
    data = json.loads(path.read_text(encoding='utf-8'))
    retriever = retriever or Retriever(rag)
    report = dict(query_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), status=data['status'],
                  limitations=['Author-written development queries; any listed gold counts as a hit.',
                               'No legal applicability, generation or video accuracy is measured.',
                               'No score threshold is used for relevance.'], variants={})
    for mode in modes:
        for lexicon in (False, True):
            rows = []
            started = time.perf_counter()
            for q in data['queries']:
                gold = {f'{g.split(":")[0]}:rules1:p{g.split(":")[1]}' for g in q['gold']}
                docs = {g.split(':')[0] for g in q['gold']}
                retriever._query_vectors.clear()
                # Gold in this dev set belongs to the core tier. Other tiers are
                # kept separate, never interleaved to improve this score.
                hits = retriever.rank_tier('core', [(q['id'], q['text'], ())], mode, lexicon)[:20]
                rows.append(dict(id=q['id'], kind=q['kind'], gold=q['gold'],
                                 norm_rank=next((i for i, h in enumerate(hits, 1) if h.unit_id in gold), None),
                                 document_rank=next((i for i, h in enumerate(hits, 1)
                                                     if rag.source_library().units[h.unit_id].source_id in docs), None),
                                 top=[h.unit_id for h in hits[:5]]))
            groups = defaultdict(list)
            for row in rows:
                groups[row['kind']].append(row)
            report['variants'][f'{mode}_lexicon_{str(lexicon).lower()}'] = dict(
                **summary(rows), groups={g: summary(r) for g, r in groups.items()}, per_query=rows,
                total_ms=round((time.perf_counter() - started) * 1000, 2))
    return report


def run(rag, config, *, models=False, index_dir=None):
    started = time.perf_counter()
    report = dict(created_utc=datetime.now(timezone.utc).isoformat(), environment=environment(),
                  code_sha256=rag.manifest()['code_sha256'], inputs=rag.manifest(), config=config.to_dict(),
                  library=rag.source_library().summary(), real_models_run=False)
    retriever = None
    if models:
        worker = rag.runtime(config, index_dir=index_dir).warm()
        retriever = worker.retriever
        report['real_models_run'] = True
        report['model_metadata'] = dict(embedder=worker.embedder.describe() if worker.embedder else None,
                                        generator=worker.generator.describe())
    report['retrieval'] = retrieval_benchmark(rag, retriever=retriever,
                                             modes=('bm25', 'dense', 'hybrid') if models and worker.dense else ('bm25',))
    if not models:
        report['not_run'] = ['BGE-M3 dense/hybrid quality', 'Qwen A/B quality and latency',
                             'CUDA VRAM and CPU/GPU consistency', 'independent frozen test',
                             'human legal/semantic evaluation']
        cpu = config.with_device('cpu', 'float32')
        config = replace(cpu, retrieval=replace(cpu.retrieval, mode='bm25', top_k=1))
        worker = rag.runtime(config, template_only=True).warm()
    source = Path(__file__).parent / 'examples' / 'leaving_workplace.json'
    base = json.loads(source.read_text(encoding='utf-8'))
    fixtures = []
    for status, expected in (('confirmed', 'violation_supported'), ('refuted', 'refuted'), ('unknown', 'insufficient')):
        bundle = json.loads(json.dumps(base))
        bundle['bundle_id'] += '-' + status
        if status == 'unknown':
            bundle['facts'][1]['status'] = status
        else:
            bundle['facts'][0]['status'] = status
        result = worker.analyze(bundle).to_dict()
        target = [a for a in result['assessments'] if a['rule_id'] == 'R231-22']
        fixtures.append(dict(kind='synthetic_wiring_not_blind', expected=expected,
                             observed=[a['decision'] for a in target],
                             passes=bool(target) and all(a['decision'] == expected for a in target), result=result))
    bundle = json.loads(json.dumps(base)); bundle['bundle_id'] = 'synthetic-controller-exception'
    bundle['facts'] = [dict(bundle['facts'][0], fact_id='f1', predicate='cash_counting', statement='Кассир пересчитывает деньги'),
                       dict(bundle['facts'][0], fact_id='f2', predicate='controller_present',
                            statement='Контролирующий работник присутствует', status='refuted'),
                       dict(bundle['facts'][0], fact_id='f3', predicate='cash_receipt', statement='Кассир принимает деньги клиента')]
    result = worker.analyze(bundle).to_dict()
    target = [a for a in result['assessments'] if a['rule_id'] == 'R231-42']
    fixtures.append(dict(kind='synthetic_wiring_not_blind', expected='exception_applies',
                         observed=[a['decision'] for a in target], passes=bool(target) and
                         all(a['decision'] == 'exception_applies' for a in target), result=result))
    report['smoke'] = fixtures
    report['total_seconds'] = round(time.perf_counter() - started, 3)
    return report
