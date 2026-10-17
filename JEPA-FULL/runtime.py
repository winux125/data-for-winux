"""Standalone inference for the frozen JEPA classifier and single-v6 localizer."""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_spec(root=ROOT):
    root = Path(root).resolve()
    spec = json.loads((root / 'model.json').read_text(encoding='utf-8'))
    if spec['schema_version'] != 1:
        raise ValueError('Unsupported model package schema')
    for name, expected in spec['sha256'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Missing package file: {name}')
        if sha256(path) != expected:
            raise ValueError(f'Package integrity check failed: {name}')
    return spec


class Heads:
    """CPU classifier/localizer. No video labels or annotation files are read."""
    def __init__(self, root=ROOT, spec=None):
        import joblib
        import sklearn
        self.root = Path(root).resolve()
        self.spec = spec if spec is not None else load_spec(self.root)
        if sklearn.__version__ != self.spec['sklearn_version']:
            raise RuntimeError('Use scikit-learn==' + self.spec['sklearn_version'] +
                               '; serialized model versions must match.')
        self.models = joblib.load(self.root / self.spec['heads'])

    def classify(self, caches):
        from scipy.special import expit
        from forte_vlm.jepa import video_features
        total = 0.
        for name, weight in self.spec['classification_weights'].items():
            f = caches[name]
            features = video_features(f['global_embedding'], f['windows'], 'context')
            total += weight * float(expit(self.models['classifiers'][name].decision_function(features[None])[0]))
        if not math.isfinite(total) or not 0 <= total <= 1:
            raise ValueError('Nonfinite or out-of-range classification score')
        return total

    def finish(self, caches, duration, score=None):
        score = self.classify(caches) if score is None else float(score)
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Invalid classification score')
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Invalid video duration')
        positive = score >= self.spec['threshold']
        result = dict(schema_version=1, status='ok', model=self.spec['model_id'],
                      label=int(positive), label_name='нарушение' if positive else 'без нарушения',
                      violation_detected=positive, score=score,
                      score_type='uncalibrated_blend_score', threshold=self.spec['threshold'],
                      timecode_sec=None, timecode=None, events=[],
                      timestamp_status='not_applicable')
        if not positive:
            return result
        from forte_vlm.jepa_temporal_v2 import attribution, relative_scores
        from forte_vlm.jepa_single_fusion import branch_scores, one_fused
        fast = caches['localizer']
        importance = attribution(caches, self.models['classifiers'], duration, fast['starts'])
        trace = {**branch_scores(fast, self.models['localizer']),
                 'importance_normalized': relative_scores(importance).tolist()}
        old = one_fused({'id': 'input', 'duration_sec': duration}, fast, trace, score,
                        self.spec['localization_parameters'])
        if len(old['events']) > 1:
            raise ValueError('Single-timestamp model returned multiple events')
        if old['events']:
            event = old['events'][0]
            point = float(event['timecode_sec'])
            if not math.isfinite(point) or not 0 <= point <= duration:
                raise ValueError('Invalid timestamp')
            result.update(timecode_sec=point, timecode=event['timecode'],
                          timestamp_status='estimated',
                          events=[{'timecode_sec': point, 'timecode': event['timecode']}])
        else:
            result.update(timestamp_status='uncertain',
                          timestamp_message='Нарушение предсказано, но выраженного временного пика нет.')
        return result


def resolve_device(requested='auto'):
    import torch
    if requested not in ('auto', 'cpu', 'cuda'):
        raise ValueError('device must be auto, cpu or cuda')
    if requested == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    if requested == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable. Install the CUDA build/driver or use --device cpu.')
    return requested


def video_duration(video):
    # PyAV wheels include FFmpeg libraries, so no system ffprobe executable is needed.
    import av
    with av.open(str(video)) as container:
        if not container.streams.video:
            raise ValueError('No video stream')
        stream = container.streams.video[0]
        if stream.duration is not None and stream.time_base is not None:
            duration = round(float(stream.duration * stream.time_base), 6)
        elif container.duration is not None:
            duration = round(container.duration / av.time_base, 6)
        else:
            raise ValueError('Video duration missing from stream and container metadata')
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid video duration')
    return duration


def decode(video, resolution, fps):
    """Exact original sequential decode, letterbox and nearest-frame convention."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    native_fps = cap.get(cv2.CAP_PROP_FPS)
    try:
        if not cap.isOpened() or not math.isfinite(native_fps) or native_fps <= 0:
            raise RuntimeError(f'Cannot decode {video}')
        frames, times, next_t, index, box = [], [], 0., 0, None
        while cap.grab():
            t = index / native_fps
            index += 1
            if t + .5 / native_fps < next_t:
                continue
            ok, bgr = cap.retrieve()
            if not ok:
                raise RuntimeError(f'Failed frame {index} in {video}')
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            scale = resolution / max(h, w)
            rh, rw = round(h * scale), round(w * scale)
            top, left = (resolution - rh) // 2, (resolution - rw) // 2
            box = (top, left, rh, rw)
            canvas = np.empty((resolution, resolution, 3), dtype=np.uint8)
            canvas[:] = [124, 116, 104]
            canvas[top:top + rh, left:left + rw] = cv2.resize(rgb, (rw, rh), interpolation=cv2.INTER_AREA)
            frames.append(canvas)
            times.append(t)
            next_t += 1 / fps
        if not frames:
            raise RuntimeError(f'Empty video {video}')
        return np.stack(frames), np.array(times), box
    finally:
        cap.release()


class JepaModel:
    """Load once, then call predict(path) for any number of ordinary videos."""
    def __init__(self, package_dir=ROOT, device='auto', threads=4):
        import cv2
        import torch
        from threadpoolctl import threadpool_limits
        self.root = Path(package_dir).resolve()
        self.spec = load_spec(self.root)
        self.device = resolve_device(device)
        self.precision = 'bfloat16' if self.device == 'cuda' and torch.cuda.is_bf16_supported() else 'float32'
        if not isinstance(threads, int) or threads < 1:
            raise ValueError('threads must be a positive integer')
        self.threads = threads
        torch.set_num_threads(threads)
        cv2.setNumThreads(2)
        torch.manual_seed(self.spec['seed'])
        torch.backends.cudnn.benchmark = False
        sys.path.insert(0, str(self.root / 'vendor' / 'vjepa2'))
        from app.vjepa_2_1.models.vision_transformer import vit_large
        self._vit_large = vit_large
        self._state = torch.load(self.root / self.spec['encoder'], map_location='cpu', weights_only=True, mmap=True)
        self._encoders = {}
        self.heads = Heads(self.root, self.spec)
        self._threadpool_limits = threadpool_limits
        self._mean = torch.tensor([.485, .456, .406], device=self.device)[None, :, None, None, None]
        self._std = torch.tensor([.229, .224, .225], device=self.device)[None, :, None, None, None]
        self.last_run = {}

    def _encoder(self, count):
        if count not in self._encoders:
            model = self._vit_large(img_size=(384, 384), num_frames=count, patch_size=16,
                tubelet_size=2, uniform_power=False, use_rope=True,
                img_temporal_dim_size=1, interpolate_rope=True, use_sdpa=True)
            model.load_state_dict(self._state, strict=True, assign=True)
            self._encoders[count] = model.eval().requires_grad_(False).to(self.device)
        return self._encoders[count]

    def _features(self, decoded, duration, view, include_global=True):
        import torch
        from forte_vlm.jepa import clip_indices, window_starts
        from forte_vlm.dino import region_masks
        frames, times, box = decoded
        count = view['frames_per_clip']
        model = self._encoder(count)
        masks = [torch.tensor(m, device=self.device) for m in region_masks(box, 384, 16)]

        def encode(start, end):
            indices = clip_indices(times, start, end, count)
            x = torch.from_numpy(frames[indices]).permute(3, 0, 1, 2)[None].to(self.device).float() / 255
            x = (x - self._mean) / self._std
            mixed = torch.autocast('cuda', dtype=torch.bfloat16) if self.precision == 'bfloat16' else nullcontext()
            with torch.inference_mode(), mixed:
                tokens = model(x).float().reshape(1, count // 2, 24, 24, model.embed_dim)
                embedding = torch.stack([tokens[0, :, m, :].mean((0, 1)) for m in masks])
            values = embedding.cpu().numpy()
            if not np.isfinite(values).all():
                raise ValueError('Nonfinite encoder features')
            return values

        global_embedding = encode(0, duration) if include_global else None
        starts = np.array(window_starts(duration, view['window_sec'], view['stride_sec']))
        windows = np.stack([encode(start, min(start + view['window_sec'], duration)) for start in starts])
        return dict(global_embedding=global_embedding, windows=windows, starts=starts)

    def predict(self, video):
        import torch
        started = time.monotonic()
        video = Path(video).expanduser().resolve()
        if not video.is_file():
            raise FileNotFoundError(video)
        duration = video_duration(video)
        self.last_run = {'localizer_encoded': False, 'encoded_views': []}
        if self.device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
        views = self.spec['views']
        caches = {}
        decoded = decode(video, 384, views['jepa']['sample_fps'])
        caches['jepa'] = self._features(decoded, duration, views['jepa'])
        self.last_run['encoded_views'].append('jepa')
        del decoded
        decoded = decode(video, 384, views['longdense']['sample_fps'])
        caches['longdense'] = self._features(decoded, duration, views['longdense'])
        self.last_run['encoded_views'].append('longdense')
        with self._threadpool_limits(limits=1):
            score = self.heads.classify(caches)
        if score >= self.spec['threshold']:
            # Keep the full CPU thread count during encoder inference, including the localizer.
            caches['localizer'] = self._features(decoded, duration, views['localizer'], include_global=False)
            self.last_run.update(localizer_encoded=True)
            self.last_run['encoded_views'].append('localizer')
        with self._threadpool_limits(limits=1):
            result = self.heads.finish(caches, duration, score)
        del decoded
        if self.device == 'cuda':
            torch.cuda.synchronize()
        self.last_run.update(peak_vram_gb=torch.cuda.max_memory_allocated() / 1024**3 if self.device == 'cuda' else None)
        result.update(video=str(video), duration_sec=duration,
                      latency_sec=time.monotonic() - started, device=self.device,
                      encoder_precision=self.precision, cpu_threads=self.threads,
                      model_manifest_sha256=sha256(self.root / 'model.json'))
        return result
