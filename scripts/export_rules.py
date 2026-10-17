"""Export source card metadata without changing activation flags."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
cards = json.loads((root/'ForteBank-Legal-RAG-2026-10-18/legal_rag/data/rule_cards.json').read_text(encoding='utf-8'))
rows = [{'id': c['rule_id'], 'type': c['type_label_ru'], 'clauses': c['clause_ids'],
         'human_reviewed': c['review']['human_reviewed'],
         'production_active': c['review']['production_active'],
         'review_status': 'reviewed' if c['review']['human_reviewed'] else 'draft_requires_human_review'}
        for c in cards['cards']]
(root/'config/rules_public.json').write_text(json.dumps({'jurisdiction': 'KZ', 'rules': rows},
                                                       ensure_ascii=False, indent=2), encoding='utf-8')
