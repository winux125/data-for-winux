"""Nonlinear within-video JEPA point-heatmap rankers; train annotations only."""
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler,Normalizer
from sklearn.linear_model import Ridge
from sklearn.kernel_ridge import KernelRidge
from forte_vlm.jepa_temporal_v2 import ranking_data


def rank_key(p):
    return f"{p['rank_model']}/{p['sigma']:g}/{p['alpha']:g}/{p.get('gamma',0):g}"


def fit_ranker(rows,caches,indices,params):
    x,y,w,details=ranking_data(rows,caches,indices,params['sigma'])
    scale=StandardScaler().fit(x,sample_weight=w);z=scale.transform(x)
    if params['rank_model']=='linear':
        model=Pipeline([('scale',scale),('ridge',Ridge(alpha=params['alpha'],solver='cholesky').fit(z,y,sample_weight=w))])
    elif params['rank_model']=='rbf':
        norm=Normalizer().fit(z);z=norm.transform(z)
        learner=KernelRidge(alpha=params['alpha'],kernel='rbf',gamma=params['gamma']).fit(z,y,sample_weight=w)
        model=Pipeline([('scale',scale),('normalize',norm),('kernel',learner)])
    else:raise ValueError('Unknown point-ranker model')
    return model,{'fitting_indices':list(indices),'positive_parents':details,'rows':len(x),
        'parent_weight_total':float(w.sum()),'sigma':params['sigma'],'alpha':params['alpha'],
        'rank_model':params['rank_model'],'gamma':params.get('gamma',0.)}
