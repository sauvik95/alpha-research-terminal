"""Index membership: public pages for large-cap indices; IWM ETF proxy for Russell 2000.
Russell holdings are NOT the official Russell 2000 constituent file.
"""
import io
import os
import re
import urllib.request
from datetime import datetime, timezone
import pandas as pd

WIKI = 'https://en.wikipedia.org/wiki/'
PAGES = {
    'SP500': ('List_of_S%26P_500_companies', 'Symbol', 450, 550),
    'NASDAQ100': ('Nasdaq-100', 'Ticker', 90, 125),
    'DOW30': ('Dow_Jones_Industrial_Average', 'Symbol', 25, 35),
}
IWM_URL = ('https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/'
           '1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund')


def download(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; ResearchTerminal/1.0)'})
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read().decode('utf-8-sig')


def normalize(ticker):
    ticker = str(ticker).strip().upper().replace('.', '-')
    return ticker if re.fullmatch(r'[A-Z][A-Z0-9-]{0,11}', ticker) else None


def large_cap(index):
    slug, column, minimum, maximum = PAGES[index]
    tables = pd.read_html(io.StringIO(download(WIKI + slug)))
    candidates = []
    for table in tables:
        cols = {str(c).strip().lower(): c for c in table.columns}
        target = cols.get(column.lower())
        if target is None:
            # Wikipedia sometimes uses 'Ticker symbol' or 'Ticker'.
            target = next((c for c in table.columns if str(c).strip().lower() in
                           ('ticker symbol', 'ticker', 'symbol')), None)
        if target is None:
            continue
        tickers = list(dict.fromkeys(filter(None, (normalize(v) for v in table[target].dropna()))))
        if minimum <= len(tickers) <= maximum:
            candidates.append(tickers)
    if not candidates:
        raise RuntimeError(f'{index}: no valid constituent table found; source may have changed')
    return max(candidates, key=len)


def russell_proxy():
    """Fetch iShares IWM ETF equity holdings; proxy, not official index membership."""
    content = download(os.getenv('IWM_HOLDINGS_URL', IWM_URL))
    lines = content.splitlines()
    header = next((i for i, line in enumerate(lines) if line.lstrip('\ufeff\"').startswith('Ticker,')
                   or line.lstrip('\ufeff\"').startswith('Ticker","')), None)
    if header is None:
        raise RuntimeError('IWM CSV header not found; check source URL')
    df = pd.read_csv(io.StringIO('\n'.join(lines[header:])), on_bad_lines='skip')
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    if 'Ticker' not in df.columns:
        raise RuntimeError('IWM holdings file missing Ticker column')
    if 'Asset Class' in df.columns:
        df = df[df['Asset Class'].astype(str).str.lower().eq('equity')]
    tickers = list(dict.fromkeys(filter(None, (normalize(x) for x in df['Ticker'].dropna()))))
    if not 1500 <= len(tickers) <= 2500:
        raise RuntimeError(f'IWM equity holdings unexpectedly numbered {len(tickers)}')
    return tickers


def build_universe(indices):
    memberships = {}
    sources = {}
    failures = {}
    for index in indices:
        try:
            tickers = russell_proxy() if index == 'RUSSELL2000' else large_cap(index)
            sources[index] = 'iShares IWM ETF holdings proxy (NOT official index)' if index == 'RUSSELL2000' else 'Wikipedia constituent table'
            for ticker in tickers:
                memberships.setdefault(ticker, []).append(index)
        except Exception as exc:
            failures[index] = str(exc)
    if failures:
        # Never silently claim all requested indices were loaded.
        raise RuntimeError(f'Universe source failures: {failures}')
    return {'as_of_utc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
            'memberships': memberships, 'counts': {i: sum(i in v for v in memberships.values()) for i in indices}}
