"""Label-independent sampling and pooling for the frozen video encoder."""
import numpy as np


def window_starts(duration, width=8., stride=4.):
    if duration <= 0 or width <= 0 or stride <= 0:
        raise ValueError('Durations and stride must be positive')
    last = max(0., duration - width)
    starts = list(np.arange(0., last + 1e-7, stride))
    if last - starts[-1] > 1e-6:
        starts.append(last)
    return starts


def clip_indices(times, start, end, count=16):
    targets = np.linspace(start, end, count, endpoint=False)
    # Nearest actually decoded frame, also deterministic for short videos.
    return np.abs(np.asarray(times)[:, None] - targets[None, :]).argmin(axis=0)


def video_features(global_embedding, windows, mode):
    """One vector per video; no window inherits its video's positive label."""
    g = np.asarray(global_embedding, dtype=np.float32).reshape(-1)
    if mode == 'global':
        return g
    w = np.asarray(windows, dtype=np.float32).reshape(len(windows), -1)
    thirds = [part.mean(0) for part in np.array_split(w, 3)] if len(w) >= 3 else [w.mean(0)] * 3
    change = np.abs(np.diff(w, axis=0)).mean(0) if len(w) > 1 else np.zeros_like(w[0])
    return np.concatenate([g, w.mean(0), w.std(0), w.max(0), change, *thirds])
