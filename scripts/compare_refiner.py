"""Private development comparison. Prints counts/timings, never video descriptions."""
import dataclasses
import json
import logging
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root/'JEPA-FULL'))
sys.path.insert(0, str(root/'ForteBank-Legal-RAG-2026-10-18'))
logging.basicConfig(level=logging.INFO)

import torch
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration
from legal_rag import shared
from legal_rag.config import load_config
from legal_rag.generate import QwenTextGenerator
from legal_rag.pipeline import LegalRAGRuntime
from backend.vision import VisualObserver
from backend.optimizations import optimize_visual_patch_embedding
from backend.video import sample, metadata
from backend.pipeline import observation_bundle
from backend.legal import assess
from runtime import JepaModel

torch.set_num_threads(8)
config = load_config(root/'ForteBank-Legal-RAG-2026-10-18/configs/cpu_smoke.json')
local = '/ephemeral/forte-service-models/qwen3-vl-32b'
g = QwenTextGenerator.__new__(QwenTextGenerator)
g.torch, g.config = torch, dataclasses.replace(config.generator, model_id=local, revision=None, device='cuda:0', dtype='bfloat16')
g.processor = AutoProcessor.from_pretrained(local, local_files_only=True)
started = time.monotonic()
g.model = Qwen3VLForConditionalGeneration.from_pretrained(local, local_files_only=True, dtype=torch.bfloat16,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True),
    device_map={'':'cuda:0'}, attn_implementation='sdpa').eval()
g.name, g.load_seconds = 'Qwen3-VL-32B-Instruct-NF4', time.monotonic()-started
optimize_visual_patch_embedding(g.model)
rag = shared()
runtime = LegalRAGRuntime(rag, config, template_only=True).warm()
observer = VisualObserver(g, rag.cards_meta['predicate_vocabulary']['canonical']+['other_observed_action'])
observer.generation_timeout = 90
detector = JepaModel(device='cuda', threads=8)
out = Path('/ephemeral/forte-service-evaluation/32b')
out.mkdir(parents=True, exist_ok=True)
for video in sys.argv[1:]:
    path = Path(video)
    started = time.monotonic()
    binary = detector.predict(path)
    duration = metadata(path)
    peak = binary.get('timecode_sec')
    peak = peak if peak is not None else duration/2
    frames = sample(path, [max(0,min(duration-.05,peak+o)) for o in [-4,-3,-2,-1,0,1,2,3,4]])
    try:
        candidates = observer.observe(frames)
    except Exception as exc:
        (out/(path.stem+'-invalid.txt')).write_text(getattr(observer,'last_response',''),encoding='utf-8')
        print(json.dumps({'file':path.name,'error_type':type(exc).__name__,
                          'elapsed_sec':round(time.monotonic()-started,2)}),flush=True)
        continue
    assessments = []
    for index,event in enumerate(candidates):
        assessments.extend(assess(runtime, observation_bundle(event,index),allow_advisory=True))
    count = sum(a['decision']=='violation_supported' or a.get('advisory_visible_trigger',False) for a in assessments)
    private = {'candidates':[{k:v for k,v in event.items() if k!='frames'} for event in candidates], 'assessments':assessments}
    (out/(path.stem+'.json')).write_text(json.dumps(private,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'file':path.name,'detector_positive':binary['label'], 'candidate_count':len(candidates),
                      'grounded_count':count,'elapsed_sec':round(time.monotonic()-started,2)}),flush=True)
