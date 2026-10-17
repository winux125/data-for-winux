"""Transport around the supplied JEPA and RAG public APIs; no decision overrides."""
import hashlib
import dataclasses
import json
import logging
import sys
import time

from .settings import ROOT
from .video import metadata, sample
from .vision import VisualObserver
from .legal import assess, publishable_assessments

sys.path.insert(0, str(ROOT / 'JEPA-FULL'))
sys.path.insert(0, str(ROOT / 'ForteBank-Legal-RAG-2026-10-18'))
log = logging.getLogger(__name__)


class AnalysisUnavailable(ValueError):
    """A processing failure, never a third or a clean verdict."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def observation_bundle(events):
    actors, facts = [], []
    for index, event in enumerate(events):
        point = round(event['time'], 4)
        actor = f'cashier{index}'
        refs = [f'frame:{f.timestamp:.4f}' for f in event['frames']]
        rows = [{'t_start': point, 't_end': point, 'anchor_sec': point, 'evidence_refs': refs,
                 **fact, 'fact_id': f'e{index}_f{i}', 'actor_id': actor, 'operation_id': f'event{index}'}
                for i, fact in enumerate(event['facts'])]
        facts.extend(rows)
        # IDs express scope within this observation, never biometric identity.
        actors.append({'actor_id': actor, 'role': 'cashier',
                       'role_status': 'confirmed' if event['role_visible'] else 'unknown',
                       'fact_ids': [f['fact_id'] for f in rows]})
    return {'schema': 'legal_rag.input.v1', 'bundle_id': 'video_observations',
            'context': {'organization_type': 'bank', 'event_date': None},
            'actors': actors, 'facts': facts,
            'provenance': {'source': 'local_visual_observer'}}


def event_for_assessment(assessment, events):
    operation = assessment.get('validation', {}).get('scope', {}).get('operation_id')
    if operation is not None:
        return next((e for i, e in enumerate(events) if operation == f'event{i}'), None)
    # General readings may omit scope. Map only unambiguous cited fact IDs.
    cited = {row['fact_id'].split('_')[0] for row in assessment.get('evidence', [])}
    matches = [e for i, e in enumerate(events) if f'e{i}' in cited]
    return matches[0] if len(matches) == 1 else None


class Pipeline:
    def __init__(self):
        import torch
        from runtime import JepaModel
        from legal_rag import shared
        from legal_rag.config import load_config, ModelConfig
        from legal_rag.generate import QwenTextGenerator
        from legal_rag.pipeline import LegalRAGRuntime
        from legal_rag.embed import BgeM3Embedder, build_index
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA GPU required for the five minute service')
        digest = hashlib.sha256()
        for file in sorted((ROOT / 'backend').glob('*.py')):
            digest.update(file.name.encode())
            digest.update(file.read_bytes())
        self.build_id = digest.hexdigest()[:16]
        torch.set_num_threads(8)
        self.jepa = JepaModel(device='cuda', threads=8)
        # The supplied RAG config, model, retrieval, generation and gates are intact.
        config = load_config(ROOT / 'ForteBank-Legal-RAG-2026-10-18/configs/cuda.json')
        # Resolve the SAME pinned revisions to disk. Transformers 4.57 otherwise
        # tries a model-info request from AutoTokenizer despite local_files_only.
        from huggingface_hub import snapshot_download
        def on_disk(model):
            path = snapshot_download(model.model_id, revision=model.revision, local_files_only=True)
            return dataclasses.replace(model, model_id=path)
        config = dataclasses.replace(config, embedder=on_disk(config.embedder), generator=on_disk(config.generator))
        self.rag = shared()
        index = ROOT / 'data' / 'legal_index_stock'
        embedder = BgeM3Embedder(config.embedder)
        if not (index / 'manifest.json').exists():
            build_index(self.rag.source_library(), embedder, index)
        self.legal = LegalRAGRuntime(self.rag, config, embedder=embedder, index_dir=index).warm()
        # Separate visual observation adapter: RAG accepts structured facts, not video.
        observer_config = json.loads((ROOT / 'config/observer.json').read_text())
        observer_config['model_id'] = str(ROOT / observer_config['model_id'])
        generator = QwenTextGenerator(ModelConfig(**observer_config))
        from .optimizations import optimize_visual_patch_embedding
        optimize_visual_patch_embedding(generator.model)
        vocabulary = self.rag.cards_meta['predicate_vocabulary']['canonical']
        self.observer = VisualObserver(generator, vocabulary + ['other_observed_action'])
        log.info('Models ready; original JEPA and RAG public interfaces')

    def analyze(self, path, stage):
        started = time.monotonic()
        duration = metadata(path)
        stage('detecting')
        binary = self.jepa.predict(path)
        log.info('JEPA duration=%.2f inference=%.2f label=%s', duration, binary['latency_sec'], binary['label'])
        stage('observing')
        # A bounded overview plus the detector's local window. The earlier
        # overlapping 24s windows could use the entire SLA before RAG started.
        count = min(24, max(12, int(duration / 2) + 1))
        windows = [[max(0., duration - .05) * i / (count - 1) for i in range(count)]]
        peak = binary.get('timecode_sec')
        if peak is not None:
            windows.insert(0, [max(0., min(duration - .05, peak + offset)) for offset in (-3, -2, -1, 0, 1, 2, 3)])
        frames = sample(path, [t for window in windows for t in window])
        candidates = []
        for window in windows:
            selected = list({f.timestamp: f for f in
                (min(frames, key=lambda f: abs(f.timestamp - t)) for t in window)}.values())
            candidates.extend(self.observer.observe(selected))
        stage('checking_rules')
        result = assess(self.legal, observation_bundle(candidates)) if candidates else {'assessments': []}
        # Persist the exact local RAG response for diagnosis, outside public routes.
        # Nothing in this record is sent to an external model or to the browser.
        from pathlib import Path
        from .settings import DATA
        audit = DATA / 'legal-audit'
        audit.mkdir(mode=0o700, exist_ok=True)
        (audit / (Path(path).stem + '.json')).write_text(json.dumps({
            'bundle': observation_bundle(candidates), 'result': result,
            'technical': {'candidates': len(candidates),
                'assessments': len(result['assessments']),
                'decisions': {d: sum(a.get('decision') == d for a in result['assessments'])
                    for d in sorted({a.get('decision', 'unknown') for a in result['assessments']})}}},
            ensure_ascii=False), encoding='utf-8')
        violations = []
        for assessment in publishable_assessments(result):
            event = event_for_assessment(assessment, candidates)
            if event is None:
                raise AnalysisUnavailable('evidence_scope_unresolved')
            rule_id, norm = assessment.get('rule_id'), assessment['norm']
            if any(v.get('rule_id') == rule_id and abs(v['timecode_sec'] - event['time']) < 7 for v in violations):
                continue
            rule = {'title': norm['title'], 'quote': norm['quote']}
            if norm.get('unit_label'):
                rule['section'] = norm['unit_label']
            if norm.get('official_url'):
                rule['url'] = norm['official_url']
            cited = {ref for row in assessment.get('evidence', []) for ref in row.get('evidence_refs', [])}
            support = [f for f in event.get('support_frames', event['frames']) if f'frame:{f.timestamp:.4f}' in cited]
            evidence = list({f.timestamp: f for f in [event['frames'][0], *support, *event['frames']]}.values())[:3]
            violations.append({'type': self.rag.cards[rule_id].type_label_ru if rule_id else norm['title'],
                'timecode_sec': round(event['time'], 4), 'description': assessment['explanation_text'],
                'evidence_frames': [f.evidence() for f in evidence],
                'rule_id': rule_id, 'rule': rule, 'legal_decision': assessment['decision'],
                'human_review_required': True})
        blocked = [a for a in result['assessments'] if a.get('decision') == 'violation_supported'
                   and a.get('publishable', {}).get('allowed') is not True]
        if blocked and not violations:
            raise AnalysisUnavailable('publication_not_allowed')
        if not violations and (binary['violation_detected'] or any(
                a.get('decision') in ('insufficient', 'no_norm')
                and event_for_assessment(a, candidates) is not None
                for a in result['assessments'])
                or (candidates and not result['assessments'])):
            raise AnalysisUnavailable('evidence_insufficient')
        violations.sort(key=lambda v: v['timecode_sec'])
        return {'verdict': 'violation' if violations else 'no_violation', 'violations': violations,
                'build_id': self.build_id, 'processing_sec': round(time.monotonic() - started, 3),
                'duration_sec': duration,
                'limitations': ['Результат требует проверки человеком.',
                    'Разреженная выборка кадров может пропускать короткие действия.'],
                'model_versions': {'detector': 'JEPA-FULL', 'observer': 'Qwen3-VL-8B-Instruct',
                    'legal': 'original configs/cuda.json: Qwen3-VL-4B + BGE-M3/BM25'}}
