"""Point-supervised JEPA window ranking; video classification remains independent."""
import math
import numpy as np
from forte_vlm.metrics import localization, point_matches


def window_features(windows):
    """Only pixels: local embedding and deviation from this video's mean window."""
    w = np.asarray(windows, dtype=np.float32)
    if w.ndim != 3 or w.shape[1:] != (5, 1024) or not len(w) or not np.isfinite(w).all():
        raise ValueError('Expected finite W x 5 x 1024 pooled JEPA windows')
    w = w.reshape(len(w), -1)
    return np.concatenate([w, w - w.mean(axis=0, keepdims=True)], axis=1)


def training_windows(rows, caches, indices, window_sec=4., max_negative_windows=12):
    """Use annotated positive windows and negative-video windows. Unknowns stay unlabeled."""
    matrices, labels, weights, parents, details = [], [], [], [], []
    binary = [int(rows[i]['label']) for i in indices]
    if set(binary) != {0, 1}:
        raise ValueError('Fitting parents must contain both classes')
    counts = {v: binary.count(v) for v in [0, 1]}
    for i in indices:
        row = rows[i]
        if row.get('split') != 'train':
            raise ValueError('Only train annotations may supervise localization')
        cache = caches[row['id']]
        starts = np.asarray(cache['starts'], dtype=float)
        end = np.minimum(starts + window_sec, row['duration_sec'])
        if row['label']:
            points = row['event_points_sec']
            if not points or any(not math.isfinite(t) or t < 0 or t > row['duration_sec'] for t in points):
                raise ValueError('Positive training video needs valid official point labels')
            selected = np.flatnonzero(np.any([(starts <= t) & (t <= end) for t in points], axis=0))
        else:
            selected = np.unique(np.rint(np.linspace(0, len(starts) - 1, min(max_negative_windows, len(starts)))).astype(int))
        if not len(selected):
            raise ValueError('Annotated training video has no eligible windows')
        x = window_features(cache['windows'])[selected]
        mass = len(indices) / (2 * counts[row['label']])
        matrices.append(x)
        labels.extend([row['label']] * len(selected))
        weights.extend([mass / len(selected)] * len(selected))
        parents.extend([row['id']] * len(selected))
        details.append({'id': row['id'], 'window_indices': selected.tolist(), 'label': row['label'], 'parent_weight': mass})
    return (np.concatenate(matrices), np.array(labels), np.array(weights), parents, details)


def format_time(seconds):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Invalid time')
    total = round(seconds * 1000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def peak_intervals(starts, values, duration, min_score=.5, max_events=1, window_sec=4., separation_sec=6.):
    starts, values = np.asarray(starts, float), np.asarray(values, float)
    if (starts.ndim != 1 or values.shape != starts.shape or not len(starts) or
        not np.isfinite(starts).all() or not np.isfinite(values).all() or
        np.any(values < 0) or np.any(values > 1) or np.any(starts < 0) or
        not math.isfinite(duration) or duration <= 0 or np.any(starts >= duration) or
        not 0 <= min_score <= 1 or max_events not in [1, 2] or window_sec <= 0 or separation_sec < 0):
        raise ValueError('Invalid local window predictions')
    ends = np.minimum(starts + window_sec, duration)
    centers = (starts + ends) / 2
    chosen = []
    for index in sorted(range(len(starts)), key=lambda i: (-values[i], centers[i])):
        if values[index] < min_score:
            continue
        if any(abs(centers[index] - centers[j]) < separation_sec for j in chosen):
            continue
        chosen.append(index)
        if len(chosen) >= max_events:
            break
    return [{'timecode_sec': float(centers[i]), 'timecode': format_time(centers[i]),
             'start_sec': float(starts[i]), 'end_sec': float(ends[i]),
             'start_timecode': format_time(starts[i]), 'end_timecode': format_time(ends[i]),
             'score': float(values[i]), 'type': 'suspected_violation',
             'description': 'Подозрительный фрагмент; границы события приблизительные.',
             'localization_kind': 'candidate_window', 'window_index': int(i)} for i in chosen]


def attach_timestamps(video_id, video_score, duration, starts, local_scores, parameters):
    """No annotation, filename or label argument: safe for ordinary new videos."""
    if not math.isfinite(video_score) or not 0 <= video_score <= 1:
        raise ValueError('Invalid video score')
    base = {'id': video_id, 'status': 'ok', 'score': float(video_score),
            'violation_detected': bool(video_score >= .5), 'events': [], 'candidate_intervals': [],
            'localization_status': 'not_applicable', 'timestamp_precision': 'approximate 4-second candidate windows',
            'localization_score_kind': 'uncalibrated window ranking score'}
    # Validate even when the classification gate is closed.
    candidates = peak_intervals(starts, local_scores, duration, min_score=0., max_events=2)
    if video_score < .5:
        return base
    base['events'] = peak_intervals(starts, local_scores, duration,
                                   min_score=parameters['min_score'], max_events=parameters['max_events'])
    base['candidate_intervals'] = candidates
    base['localization_status'] = 'ok' if base['events'] else 'uncertain'
    if not base['events']:
        base['localization_message'] = 'Нарушение обнаружено, но надёжный таймкод не определён; доступны кандидаты для просмотра.'
    return base


def point_metrics(rows, predictions):
    result = localization(rows, predictions, .5)
    expected = {r['id'] for r in rows}
    if {p['id'] for p in predictions} != expected or len(predictions) != len(rows):
        raise ValueError('Prediction coverage must be exact')
    by_id = {p['id']: p for p in predictions}
    n_gt = sum(len(r['event_points_sec']) for r in rows)
    n_pred = sum(len(p['events']) for p in predictions if p['score'] >= .5)
    result['predicted_event_count'] = n_pred
    result['negative_video_event_count'] = sum(len(by_id[r['id']]['events']) for r in rows if not r['label'])
    for tolerance in [1, 2, 5]:
        hits = sum(point_matches(r['event_points_sec'], [e['timecode_sec'] for e in by_id[r['id']]['events']], tolerance) for r in rows)
        result[f'matched_points_at_{tolerance}s'] = hits
        result[f'diagnostic_point_f1_at_{tolerance}s'] = 2 * hits / (n_gt + n_pred) if n_gt + n_pred else 0.
    return result
