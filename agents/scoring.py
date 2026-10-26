"""Deterministic, auditable research agents. Scores are not probabilities."""
import math
import numpy as np
import pandas as pd

def finite(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):
        return None

def bounded(x):
    return round(max(0,min(100,float(x))),1)

def fundamental(info):
    fields={'revenue_growth':finite(info.get('revenueGrowth')),
            'earnings_growth':finite(info.get('earningsGrowth')),
            'return_on_equity':finite(info.get('returnOnEquity')),
            'forward_pe':finite(info.get('forwardPE')),
            'debt_to_equity':finite(info.get('debtToEquity'))}
    parts,notes=[],[]
    for key,low,high in [('revenue_growth',-.15,.35),('earnings_growth',-.25,.50),('return_on_equity',-.10,.35)]:
        v=fields[key]
        if v is not None:
            parts.append(bounded(100*(v-low)/(high-low)))
            notes.append(f'{key}: {v:.1%}')
    pe=fields['forward_pe']
    if pe is not None and pe>0:
        parts.append(bounded(100*(65-pe)/55));notes.append(f'forward P/E: {pe:.1f}')
    dte=fields['debt_to_equity']
    if dte is not None and dte>=0:
        parts.append(bounded(100*(250-dte)/250));notes.append(f'debt/equity: {dte:.1f} (Yahoo units)')
    return {'score':round(float(np.mean(parts)),1) if parts else None,'coverage':len(parts),
            'metrics':fields,'evidence':notes,'caution':'Yahoo fundamentals may be stale, missing or incomparable across sectors.'}

def technical(close):
    if len(close)<200:
        return {'score':None,'coverage':0,'evidence':['Fewer than 200 price observations']}
    p=float(close.iloc[-1]);ma50=float(close.tail(50).mean());ma200=float(close.tail(200).mean())
    ret63=p/float(close.iloc[-64])-1 if len(close)>=64 else None
    ret126=p/float(close.iloc[-127])-1 if len(close)>=127 else None
    r=close.pct_change().dropna()
    vol=float(r.tail(63).std()*np.sqrt(252)) if len(r)>=63 else None
    score=bounded(35*(p>ma200)+25*(ma50>ma200)+20*(ret63 is not None and ret63>0)+20*(ret126 is not None and ret126>0))
    return {'score':score,'coverage':4,'metrics':{'price':p,'ma50':ma50,'ma200':ma200,'return_3m':ret63,
            'return_6m':ret126,'vol_3m_annualized':vol},'evidence':[f'Price above 200d MA: {p>ma200}',
            f'50d above 200d MA: {ma50>ma200}',f'3m momentum: {ret63:.1%}',f'6m momentum: {ret126:.1%}']}

def quantitative(close,benchmark):
    close = close.copy()
    benchmark = benchmark.copy()

    close.index = pd.to_datetime(close.index, utc=True).tz_localize(None).normalize()
    benchmark.index = pd.to_datetime(benchmark.index, utc=True).tz_localize(None).normalize()

    pair=pd.concat([close.pct_change().rename('stock'),benchmark.pct_change().rename('benchmark')],axis=1).dropna().tail(252)
    if len(pair)<100:
        return {'score':None,'coverage':0,'evidence':['Insufficient overlapping return history']}
    s=pair['stock'];b=pair['benchmark'];bv=float(b.var());beta=float(s.cov(b)/bv) if bv>0 else None
    alpha=float((s.mean()-(beta or 0)*b.mean())*252) if beta is not None else None
    vol=float(s.std()*np.sqrt(252));peak=close.cummax();dd=float((close/peak-1).min())
    mom=float(close.iloc[-1]/close.iloc[-127]-1) if len(close)>126 else None
    parts=[bounded(50+150*(mom or 0)),bounded(100*(.85-vol)/.7),bounded(100*(.8+dd)/.8)]
    if alpha is not None:parts.append(bounded(50+150*alpha))
    return {'score':round(float(np.mean(parts)),1),'coverage':len(parts),'metrics':{'beta_1y':beta,
            'annualized_alpha_1y_approx':alpha,'annualized_vol_1y':vol,'max_drawdown_2y':dd,'momentum_6m':mom},
            'evidence':[f'1y beta: {beta:.2f}' if beta is not None else 'Beta unavailable',
            f'Annualized volatility: {vol:.1%}',f'2y max drawdown: {dd:.1%}'],
            'caution':'Historical factor proxies are not forecasts; alpha estimate is a simplified single-index estimate.'}

def committee(agents):
    weights={'fundamental':.40,'technical':.25,'quantitative':.35}
    valid={k:v['score'] for k,v in agents.items() if v.get('score') is not None}
    if len(valid)<2:
        return {'score':None,'decision':'INSUFFICIENT DATA','disagreement':None,
                'debate':['At least two independent agent scores required.']}
    score=round(sum(valid[k]*weights[k] for k in valid)/sum(weights[k] for k in valid),1)
    spread=round(max(valid.values())-min(valid.values()),1)
    decision='RESEARCH PRIORITY' if score>=70 and spread<=30 else ('WATCHLIST' if score>=55 else 'LOW PRIORITY')
    if spread>30:decision='CONTESTED — REVIEW'
    debate=[f'{k.title()} agent: {v:.1f}/100' for k,v in valid.items()]
    debate.append(f'Score dispersion: {spread:.1f} points; no consensus override without review.')
    return {'score':score,'decision':decision,'disagreement':spread,'debate':debate,
            'note':'Research ranking only; not a price target, return probability or investment recommendation.'}
