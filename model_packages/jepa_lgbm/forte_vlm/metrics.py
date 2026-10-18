"""Video classification and point matching, without inventing interval GT."""
import math
from statistics import mean, median


def classification(rows, predictions, threshold=.5):
    by_id = {p['id']: p for p in predictions}
    tp = tn = fp = fn = failed = 0
    latencies = []
    for r in rows:
        p = by_id.get(r['id'])
        if not p or p.get('status') != 'ok':
            failed += 1
            continue
        if not math.isfinite(p['score']) or not 0 <= p['score'] <= 1:
            raise ValueError('Invalid prediction score')
        pred = p['score'] >= threshold
        if r['label']:
            tp += int(pred)
            fn += int(not pred)
        else:
            fp += int(pred)
            tn += int(not pred)
        if 'latency_sec' in p:
            latencies.append(p['latency_sec'])
    def div(a, b):
        return a / b if b else None
    recall, specificity = div(tp, tp + fn), div(tn, tn + fp)
    valid = tp + tn + fp + fn
    # Metrics on processed cases are labeled; missing cases separately lower
    # end-to-end accuracy and must never disappear from a favorable report.
    result = {'n_expected': len(rows), 'n_processed': valid, 'n_failed_or_missing': failed,
              'coverage': div(valid, len(rows)), 'threshold': threshold,
              'confusion': {'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn},
              'accuracy_processed': div(tp + tn, valid),
              'accuracy_end_to_end': div(tp + tn, len(rows)),
              'precision': div(tp, tp + fp), 'recall': recall, 'specificity': specificity,
              'f1': div(2 * tp, 2 * tp + fp + fn),
              'balanced_accuracy': (recall + specificity) / 2 if recall is not None and specificity is not None else None}
    if latencies:
        x = sorted(latencies)
        result['latency_median_sec'] = median(x)
        result['latency_p95_sec'] = x[min(len(x) - 1, math.ceil(.95 * len(x)) - 1)]
        result['within_300_sec'] = sum(t <= 300 for t in x)
    return result


def point_matches(gt, pred, tolerance):
    # Maximum-cardinality matching under tolerance; each prediction may match
    # only one official point. DFS avoids nearest-neighbor greedy undercounts.
    matched = {}
    def visit(i, seen):
        for j in sorted(range(len(pred)), key=lambda j: abs(gt[i] - pred[j])):
            if j in seen or abs(gt[i] - pred[j]) > tolerance:
                continue
            seen.add(j)
            if j not in matched or visit(matched[j], seen):
                matched[j] = i
                return True
        return False
    for i in range(len(gt)):
        visit(i, set())
    return len(matched)


def localization(rows, predictions, threshold=.5):
    by_id = {p['id']: p for p in predictions}
    total = sum(len(r['event_points_sec']) for r in rows)
    result = {'official_point_count': total, 'note': 'Diagnostic tolerances; organizers did not define tolerance or exhaustive event intervals.'}
    invalid = unavailable = 0
    nearest_errors = []
    for r in rows:
        p = by_id.get(r['id'], {})
        if p.get('localization_status') == 'invalid_json_or_schema':
            invalid += 1
        if p.get('localization_status') is None:
            unavailable += 1
        ts = [e['timecode_sec'] for e in p.get('events', [])] if p.get('score', 0) >= threshold else []
        if ts:
            nearest_errors.extend(min(abs(g - t) for t in ts) for g in r['event_points_sec'])
    result.update(invalid_localizations=invalid, missing_localizations=unavailable,
                  nearest_point_mae_when_prediction_exists=mean(nearest_errors) if nearest_errors else None)
    for tolerance in (1, 2, 5):
        hits = predictions_count = 0
        for r in rows:
            p = by_id.get(r['id'], {})
            ts = [e['timecode_sec'] for e in p.get('events', [])] if p.get('score', 0) >= threshold else []
            hits += point_matches(r['event_points_sec'], ts, tolerance)
            predictions_count += len(ts)
        result[f'point_recall_at_{tolerance}s'] = hits / total if total else None
        result[f'matched_prediction_fraction_at_{tolerance}s'] = hits / predictions_count if predictions_count else None
    return result
