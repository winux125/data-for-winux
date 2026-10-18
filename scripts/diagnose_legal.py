"""Print technical counts only. Never print video facts, descriptions or frames."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths=[p for p in (root/'data/legal-audit').glob('*.json') if not p.name.endswith('.input.json')]
for path in sorted(paths, key=lambda p:p.stat().st_mtime)[-3:]:
    value = json.loads(path.read_text())
    facts = value['bundle']['facts']
    rows = value['result'].get('review_findings', value['result'].get('assessments', []))
    print(json.dumps({'job_id':path.stem, **value['technical'],
        'fact_status_counts':{s:sum(f['status']==s for f in facts) for s in ('confirmed','refuted','unknown')},
        'gates':{str(r):sum(a.get('publishable',{}).get('reason')==r for a in rows)
            for r in sorted({a.get('publishable',{}).get('reason') for a in rows},key=str)},
        'unresolved_count':sum(len(a.get('missing',[])) for a in rows),
        'model_calls':value['result'].get('tokens',{}).get('model_calls'),
        'rag_time_ms':value['result'].get('timings_ms',{}).get('total')},ensure_ascii=False))
sys.path.insert(0,str(root))
from legal_rag import shared
rag=shared()
print(json.dumps({'cards':len(rag.cards),'human_reviewed':sum(c.review.human_reviewed for c in rag.cards.values()),
    'production_active':sum(c.review.production_active for c in rag.cards.values())}))
