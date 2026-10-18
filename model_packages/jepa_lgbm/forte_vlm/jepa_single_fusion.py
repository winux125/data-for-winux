"""Fuse two visual temporal traces before selecting exactly one location."""
import numpy as np
from forte_vlm.jepa_single_point import fit_model, predict_scores, one_prediction

BRANCHES = {
    'appearance': {'view': 'legacy', 'legacy': {'rank_model': 'rbf', 'sigma': 3., 'alpha': .1, 'gamma': 10.}},
    'motion': {'view': 'motion', 'sigma': 1., 'alpha': .1, 'gamma': 1.},
}


def fit_branches(rows, caches, indices):
    models, audits = {}, {}
    for name, p in BRANCHES.items():
        models[name], audits[name] = fit_model(rows, caches, indices, p)
    return models, audits


def branch_scores(cache, models):
    return {name: predict_scores(cache, models[name], p).tolist() for name, p in BRANCHES.items()}


def one_fused(row, cache, trace, video_score, parameters):
    m, a = parameters['motion_weight'], parameters['attribution_weight']
    values = (1-a)*((1-m)*np.asarray(trace['appearance'])+m*np.asarray(trace['motion']))+a*np.asarray(trace['importance_normalized'])
    proxy = {'model': {'view': 'fused'}, 'attribution_weight': 0., 'smoothing': False}
    from forte_vlm.jepa_single_point import model_key
    return one_prediction(row, cache, {'scores': {model_key(proxy['model']): values},
                          'importance_normalized': np.zeros(len(values))}, video_score, proxy)
