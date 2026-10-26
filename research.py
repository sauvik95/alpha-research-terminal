"""Multi-index, resumable research snapshot with cached fundamentals and batch prices."""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from agents.scoring import fundamental, technical, quantitative, committee
from universe import build_universe

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
ALL_INDICES = ('SP500', 'NASDAQ100', 'DOW30', 'RUSSELL2000')
FUNDAMENTAL_KEYS = ('shortName', 'currency', 'revenueGrowth', 'earningsGrowth',
                    'returnOnEquity', 'forwardPE', 'debtToEquity')


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6) if math.isfinite(float(x)) else None
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.isoformat()
    return x


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def prices_for(tickers, batch_size=45):
    output = {}
    failures = {}
    for start in range(0, len(tickers), batch_size):
        batch = tickers[start:start + batch_size]
        for attempt in range(3):
            try:
                df = yf.download(batch, period='2y', auto_adjust=True,
                                 progress=False, threads=8, group_by='ticker', timeout=35)
                if df.empty:
                    raise ValueError('empty price batch')
                for ticker in batch:
                    try:
                        series = df[ticker]['Close'] if isinstance(df.columns, pd.MultiIndex) else df['Close']
                        series = pd.to_numeric(series, errors='coerce').dropna()
                        if len(series) >= 200:
                            output[ticker] = series
                        else:
                            failures[ticker] = f'Insufficient history: {len(series)} rows'
                    except (KeyError, TypeError) as exc:
                        failures[ticker] = f'Missing price series: {exc}'
                break
            except Exception as exc:
                if attempt == 2:
                    for ticker in batch:
                        failures[ticker] = f'Price batch failed: {exc}'
                else:
                    time.sleep(2 ** attempt)
        print(f'Price batch {min(start + len(batch), len(tickers))}/{len(tickers)}', flush=True)
        time.sleep(0.3)
    return output, failures


def refresh_fundamentals(tickers, cache, max_requests, stale_days):
    now = datetime.now(timezone.utc)
    pending = []
    for ticker in tickers:
        entry = cache.get(ticker, {})
        try:
            age = now - datetime.fromisoformat(entry['updated_at'])
            fresh = age < timedelta(days=stale_days)
        except (KeyError, ValueError, TypeError):
            fresh = False
        if not fresh:
            pending.append(ticker)
    # Uncached companies are prioritized, then stale ones.
    pending.sort(key=lambda t: (t in cache, cache.get(t, {}).get('updated_at', '')))
    failures = {}
    for number, ticker in enumerate(pending if max_requests is None else pending[:max_requests], 1):
        try:
            raw = yf.Ticker(ticker).info or {}
            values = {key: clean(raw.get(key)) for key in FUNDAMENTAL_KEYS}
            if not any(values.get(k) is not None for k in FUNDAMENTAL_KEYS[2:]):
                raise ValueError('No usable fundamental fields')
            cache[ticker] = {'updated_at': now.isoformat(), 'values': values}
        except Exception as exc:
            failures[ticker] = str(exc)[:180]
        if number % 25 == 0:
            print(f'Fundamental refresh {number}/{len(pending) if max_requests is None else min(len(pending), max_requests)}', flush=True)
        time.sleep(0.25)
    return failures, len(pending), len(pending) if max_requests is None else min(len(pending), max_requests)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--indices', default='SP500,NASDAQ100,DOW30,RUSSELL2000')
    parser.add_argument('--max-fundamentals', type=int, default=None)
    parser.add_argument('--fundamental-stale-days', type=int, default=14)
    parser.add_argument('--min-price-coverage', type=float, default=0.85)
    args = parser.parse_args()
    indices = list(dict.fromkeys(s.strip().upper() for s in args.indices.split(',') if s.strip()))
    if not indices or set(indices) - set(ALL_INDICES):
        parser.error(f'Indices must be from: {ALL_INDICES}')
    if (args.max_fundamentals is not None and args.max_fundamentals < 0) or not 0 < args.min_price_coverage <= 1:
        parser.error('Invalid coverage or fundamental request settings')

    DATA.mkdir(exist_ok=True)
    universe = build_universe(indices)
    tickers = sorted(universe['memberships'])
    print(f'Universe: {len(tickers)} unique tickers; per-index: {universe["counts"]}', flush=True)
    benchmark = yf.Ticker('SPY').history(period='2y', auto_adjust=True)['Close'].dropna()
    if len(benchmark) < 200:
        raise RuntimeError('Benchmark unavailable; previous snapshot preserved')
    price_map, price_errors = prices_for(tickers)
    coverage = len(price_map) / len(tickers)
    if coverage < args.min_price_coverage:
        raise RuntimeError(f'Price coverage {coverage:.1%} below threshold; snapshot preserved')

    cache_path = DATA / 'fundamentals_cache.json'
    cache = read_json(cache_path, {})
    fund_errors, pending_count, attempted = refresh_fundamentals(
        tickers, cache, args.max_fundamentals, args.fundamental_stale_days)
    # Persist valid cache even when some stocks have no fundamentals yet.
    cache_path.write_text(json.dumps(clean(cache), indent=2) + '\n')
    results = []
    for ticker in tickers:
        close = price_map.get(ticker)
        if close is None:
            continue
        entry = cache.get(ticker, {})
        info = entry.get('values', {})
        agents = {'fundamental': fundamental(info),
                  'technical': technical(close),
                  'quantitative': quantitative(close, benchmark)}
        results.append({'ticker': ticker, 'company': info.get('shortName') or ticker,
                        'indices': universe['memberships'][ticker],
                        'price': float(close.iloc[-1]), 'currency': info.get('currency') or 'USD',
                        'as_of_price_date': str(close.index[-1].date()),
                        'fundamentals_updated_at': entry.get('updated_at'),
                        'agents': agents, 'committee': committee(agents)})
    results.sort(key=lambda r: (r['committee']['score'] is not None,
                                r['committee']['score'] or -1), reverse=True)
    stamp = datetime.now(timezone.utc)
    payload = clean({'generated_at_utc': stamp.isoformat(), 'benchmark': 'SPY',
                     'universe_type': 'multi_index', 'indices': indices,
                     'index_sources': universe['sources'], 'index_counts': universe['counts'],
                     'universe_size': len(tickers), 'results': results,
                     'price_coverage': coverage, 'price_errors': price_errors,
                     'fundamental_errors': fund_errors,
                     'fundamentals_refresh': {'pending_before_run': pending_count,
                                              'attempted_this_run': attempted,
                                              'cached_profiles': len(cache)},
                     'methodology': 'Existing deterministic screening; NOT AI inference or predicted returns.',
                     'disclaimer': 'IWM holdings approximate Russell 2000 membership. Public data can be stale or inaccurate.'})
    text = json.dumps(payload, separators=(',', ':'), ensure_ascii=False) + '\n'
    (DATA / 'latest.json').write_text(text)
    (DATA / (stamp.strftime('%Y-%m-%d') + '.json')).write_text(text)
    print(f'Wrote {len(results)} stocks; price coverage {coverage:.1%}; profiles cached {len(cache)}', flush=True)


if __name__ == '__main__':
    main()
