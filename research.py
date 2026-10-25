"""Generate a daily, versioned stock research snapshot using free public data."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf
from agents.scoring import fundamental, technical, quantitative, committee

DEFAULT_TICKERS=['NVDA','MSFT','GOOGL','AMZN','META','AMD','AVGO','PLTR','CRWD','MELI','SHOP','UBER','TSLA','RKLB','HIMS','SOFI']


def clean(obj):
    if isinstance(obj,dict): return {str(k):clean(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)): return [clean(v) for v in obj]
    if isinstance(obj,float): return round(obj,6) if pd.notna(obj) and abs(obj)!=float('inf') else None
    if isinstance(obj,(int,str,bool)) or obj is None: return obj
    return str(obj)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tickers',default=os.getenv('WATCHLIST',','.join(DEFAULT_TICKERS)))
    args=parser.parse_args()
    tickers=list(dict.fromkeys(t.strip().upper() for t in args.tickers.split(',') if t.strip()))[:50]
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        b=yf.Ticker('SPY').history(period='2y',auto_adjust=True)['Close'].dropna()
        if len(b)<100: raise RuntimeError('SPY benchmark history unavailable')
    except Exception as e:
        raise SystemExit(f'Benchmark download failed; existing snapshot preserved: {e}')
    results=[]; errors=[]
    for ticker in tickers:
        try:
            obj=yf.Ticker(ticker)
            hist=obj.history(period='2y',auto_adjust=True)
            close=hist['Close'].dropna().astype(float)
            if len(close)<200: raise ValueError(f'Only {len(close)} daily prices')
            try: info=obj.info or {}
            except Exception: info={}
            agents={'fundamental':fundamental(info),'technical':technical(close),'quantitative':quantitative(close,b)}
            results.append({'ticker':ticker,'company':info.get('shortName') or ticker,'price':float(close.iloc[-1]),
                            'currency':info.get('currency','USD'),'agents':agents,'committee':committee(agents),
                            'as_of_price_date':str(close.index[-1].date())})
            print(f'{ticker}: {results[-1]["committee"]["decision"]}')
        except Exception as e:
            errors.append({'ticker':ticker,'error':str(e)[:300]}); print(f'{ticker}: ERROR {e}')
    if not results: raise SystemExit('No successful tickers; preserving previous snapshot.')
    results.sort(key=lambda x: x['committee']['score'] if x['committee']['score'] is not None else -1,reverse=True)
    payload=clean({'generated_at_utc':stamp,'benchmark':'SPY','universe':tickers,'results':results,'errors':errors,
                   'methodology':'Transparent heuristic screening. Not AI inference, guaranteed upside, or investment advice.',
                   'disclaimer':'Free market data may be delayed, incomplete or wrong. Verify independently before investing.'})
    root=Path(__file__).parent; folder=root/'data'; folder.mkdir(exist_ok=True)
    latest=folder/'latest.json'; latest.write_text(json.dumps(payload,indent=2)+'\n')
    # Daily file history; one file per UTC date (reruns overwrite the same day).
    (folder/(datetime.now(timezone.utc).strftime('%Y-%m-%d')+'.json')).write_text(json.dumps(payload,indent=2)+'\n')
    print(f'Saved {len(results)} stocks; {len(errors)} failures.')

if __name__=='__main__': main()
