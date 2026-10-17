"""Explicit development check of public legal sources; never runs during inference."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
core = root / 'ForteBank-Legal-RAG-2026-10-18/legal_rag/resources/core'
sources = json.loads((core/'sources.json').read_text(encoding='utf-8'))['sources']

def check(source):
    try:
        request = Request(source['content_api_url'], headers={'User-Agent':'Forte-source-audit/1'})
        with urlopen(request, timeout=30) as response:
            actual = json.load(response)
        expected = json.loads((core/source['snapshot_path']).read_text(encoding='utf-8'))['content']
        return {'source_id':source['source_id'], 'available':True, 'content_identical':actual == expected}
    except Exception as exc:
        return {'source_id':source['source_id'], 'available':False, 'error':type(exc).__name__}

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    result = list(executor.map(check, sources))
(root/'data/source_revalidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
