"""JEPA context attribution and point-supervised within-video temporal ranking."""
import numpy as np
from forte_vlm.jepa import video_features
from forte_vlm.jepa_localization import peak_intervals,format_time


def centered_windows(windows):
    w=np.asarray(windows,dtype=np.float32)
    if w.ndim!=3 or w.shape[1:]!=(5,1024) or not len(w) or not np.isfinite(w).all():
        raise ValueError('Invalid JEPA windows')
    x=w.reshape(len(w),-1)
    return x-x.mean(axis=0,keepdims=True)


def relative_scores(values):
    a=np.asarray(values,dtype=float)
    if a.ndim!=1 or not len(a) or not np.isfinite(a).all():raise ValueError('Invalid temporal scores')
    spread=float(np.ptp(a))
    return np.zeros_like(a) if spread<1e-9 else (a-a.min())/spread


def attribution(caches,models,duration,candidate_starts):
    """Ablate pooled context windows, not raw frames or the full-video embedding."""
    centers=(np.asarray(candidate_starts)+np.minimum(np.asarray(candidate_starts)+4.,duration))/2
    drops=np.zeros(len(centers))
    for encoder,width in [('jepa',8.),('longdense',16.)]:
        f=caches[encoder];windows=np.asarray(f['windows']);starts=np.asarray(f['starts'])
        original=video_features(f['global_embedding'],windows,'context')
        altered=[]
        for point in centers:
            mask=(starts<point+1.)&(np.minimum(starts+width,duration)>point-1.)
            w=windows.copy()
            if mask.any() and (~mask).any():w[mask]=windows[~mask].mean(axis=0)
            altered.append(video_features(f['global_embedding'],w,'context'))
        model=models[encoder]
        base=float(model.decision_function(original[None])[0])
        drops+=.5*(base-model.decision_function(np.array(altered)))
    return drops


def ranking_data(rows,caches,indices,sigma):
    """Fit to supplied event-point heatmaps, without declaring unknown windows clean."""
    x,y,w,details=[],[],[],[]
    for i in indices:
        r=rows[i]
        if r.get('split')!='train':raise ValueError('Only train annotations allowed')
        if not r['label']:continue
        points=np.asarray(r['event_points_sec'],dtype=float)
        if not len(points) or not np.isfinite(points).all() or np.any(points<0) or np.any(points>r['duration_sec']):
            raise ValueError('Invalid train points')
        cache=caches[r['id']]['localizer'];starts=np.asarray(cache['starts'])
        centers=(starts+np.minimum(starts+4,r['duration_sec']))/2
        target=np.exp(-.5*(np.abs(centers[:,None]-points[None,:]).min(axis=1)/sigma)**2)
        target-=target.mean()
        values=centered_windows(cache['windows'])
        x.append(values);y.extend(target);w.extend([1/len(starts)]*len(starts))
        details.append({'id':r['id'],'n_windows':len(starts),'point_count':len(points),'weight_total':1.})
    if not x:raise ValueError('No positive fitting parents')
    return np.concatenate(x),np.array(y),np.array(w),details


def combine_scores(cache,rank_model,importance,mix):
    # mix is the context-attribution weight; all inputs are label-independent at inference.
    scores=relative_scores(importance)
    if mix==1:return scores
    ranks=relative_scores(rank_model.predict(centered_windows(cache['windows'])))
    return (1-mix)*ranks+mix*scores


def attach(video_id,video_score,duration,starts,values,parameters):
    starts,values=np.asarray(starts,float),np.asarray(values,float)
    # Reuse the production bounds/finite validation and temporal NMS.
    review=peak_intervals(starts,values,duration,min_score=0,max_events=2)
    output={'id':video_id,'status':'ok','score':float(video_score),'violation_detected':bool(video_score>=.5),
        'events':[],'candidate_intervals':[],'localization_status':'not_applicable',
        'timestamp_precision':'JEPA candidate window with interpolated peak; boundaries approximate',
        'localization_score_kind':'within-video relative temporal ranking, not probability'}
    if not np.isfinite(video_score) or not 0<=video_score<=1:raise ValueError('Invalid video score')
    if video_score<.5:return output
    if np.ptp(values)<1e-9:
        output.update(localization_status='uncertain',localization_message='Нет различимого временного пика; таймкод не определён.')
        return output
    events=peak_intervals(starts,values,duration,min_score=parameters['secondary_threshold'],max_events=parameters['max_events'])
    centers=(starts+np.minimum(starts+4.,duration))/2
    for event in events+review:
        i=event['window_index'];time=float(centers[i])
        if 0<i<len(values)-1:
            x=centers[i-1:i+2]-centers[i];v=values[i-1:i+2]
            a,b,_=np.polyfit(x,v,2)
            if a<-1e-12:
                shift=float(np.clip(-b/(2*a),x[0]/2,x[-1]/2))
                time=float(np.clip(time+shift,event['start_sec'],event['end_sec']))
        event.update(timecode_sec=time,timecode=format_time(time),localization_kind='temporal_peak_candidate')
    output.update(events=events,candidate_intervals=review,localization_status='ok' if events else 'uncertain')
    return output
