"""Offline wiring check. No weights, GPU, network or third-party libraries are needed."""
import json
from pathlib import Path
import sys

from legal_rag import shared
from legal_rag.config import load_config

ROOT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding='utf-8')
config = load_config(ROOT / 'configs' / 'cpu_smoke.json')
raw = json.loads((ROOT / 'legal_rag/examples/leaving_workplace.json').read_text(encoding='utf-8'))
result = shared().analyze(raw, config, template_only=True).to_dict()
target = next(a for a in result['assessments'] if a['rule_id'] == 'R231-22')
assert target['decision'] == 'violation_supported'
assert target['generator'] == 'template_fallback'
assert target['publishable']['allowed'] is False
(ROOT / 'smoke_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(rule_id=target['rule_id'], decision=target['decision'], generator=target['generator'],
                      publication_allowed=target['publishable']['allowed'],
                      source_hashes_verified=shared().source_library().summary()['source_hashes_verified']),
                 ensure_ascii=False, indent=2))
