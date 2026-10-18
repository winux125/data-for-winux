"""Single-peak localization from JEPA appearance and ordered temporal context."""
import json
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, Normalizer
from sklearn.kernel_ridge import KernelRidge
from forte_vlm.jepa_temporal_v2 import centered_windows, relative_scores, attach
from forte_vlm.jepa_point_kernel import fit_ranker


def view_features(windows, view):
    centered = centered_windows(windows)
    if view == 'centered':
        return centered
    previous = np.concatenate([centered[:1], centered[:-1]])
    following = np.concatenate([centered[1:], centered[-1:]])
    if view == 'ordered':
        return np.concatenate([previous, centered, following], axis=1)
    if view == 'motion':
        return np.concatenate([centered-previous, following-centered], axis=1)
    if view == 'appearance':
        return np.asarray(windows, np.float32).reshape(len(centered), -1)
    raise ValueError('Unknown temporal feature view')


def model_key(parameters):
    return json.dumps(parameters, sort_keys=True, separators=(',', ':'))


def fit_model(rows, caches, indices, parameters):
    if parameters['view'] == 'legacy':
        return fit_ranker(rows, caches, indices, parameters['legacy'])
    xs, ys, weights, parents = [], [], [], []
    for i in indices:
        row = rows[i]
        if row.get('split') != 'train':
            raise ValueError('Only train annotations may supervise localization')
        if not row['label'] and parameters['view'] != 'appearance':
            continue
        cache = caches[row['id']]['localizer']
        starts = np.asarray(cache['starts'], float)
        centers = (starts + np.minimum(starts+4., row['duration_sec']))/2
        target = np.zeros(len(starts))
        if row['label']:
            points = np.asarray(row['event_points_sec'], float)
            if not len(points) or not np.isfinite(points).all() or np.any(points < 0) or np.any(points > row['duration_sec']):
                raise ValueError('Invalid training annotation')
            distance = np.abs(centers[:, None]-points).min(axis=1)
            target = np.exp(-.5*(distance/parameters['sigma'])**2)
            # Absolute appearance uses clean videos as zero targets. Other views rank within the positive bag.
            if parameters['view'] != 'appearance':
                target -= target.mean()
        xs.append(view_features(cache['windows'], parameters['view']))
        ys.extend(target)
        weights.extend([1./len(starts)]*len(starts))
        parents.append({'id': row['id'], 'label': row['label'], 'windows': len(starts), 'weight_total': 1.})
    if not xs:
        raise ValueError('No fitting videos')
    x, y, w = np.concatenate(xs), np.asarray(ys), np.asarray(weights)
    scale = StandardScaler().fit(x, sample_weight=w)
    norm = Normalizer()
    z = norm.fit_transform(scale.transform(x))
    kernel = KernelRidge(alpha=parameters['alpha'], kernel='rbf', gamma=parameters['gamma']).fit(z, y, sample_weight=w)
    model = Pipeline([('scale', scale), ('normalize', norm), ('kernel', kernel)])
    return model, {'fitting_indices': list(indices), 'parents': parents, 'rows': len(x),
                   'weight_total': float(w.sum()), 'parameters': parameters}


def predict_scores(cache, model, parameters):
    view = 'centered' if parameters['view'] == 'legacy' else parameters['view']
    return relative_scores(model.predict(view_features(cache['windows'], view)))


def score_trace(trace, parameters):
    values = np.asarray(trace['scores'][model_key(parameters['model'])], float)
    mix = parameters['attribution_weight']
    values = (1-mix)*values + mix*np.asarray(trace['importance_normalized'], float)
    if parameters['smoothing'] and len(values) > 2:
        padded = np.pad(values, (1, 1), mode='edge')
        values = .25*padded[:-2]+.5*padded[1:-1]+.25*padded[2:]
    return relative_scores(values)


def one_prediction(row, cache, trace, video_score, parameters):
    result = attach(row['id'], video_score, row['duration_sec'], cache['starts'], score_trace(trace, parameters),
                    {'secondary_threshold': 0., 'max_events': 1})
    # A single estimated location is the public output, never a hidden second alternative.
    result['candidate_intervals'] = result['events'].copy()
    result['timestamp_candidates'] = result['events']
    result['event_count_estimated'] = False
    result['timestamp_semantics'] = 'one estimated location; approximate, not a confirmed event boundary'
    return result
