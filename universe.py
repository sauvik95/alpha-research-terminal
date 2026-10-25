"""Public index membership. Russell 2000 is proxied by IWM ETF holdings, not official membership."""
import csv
import io
import os
import re
import urllib.request
from datetime import datetime, timezone
import pandas as pd

WIKI = 'https://en.wikipedia.org/wiki/'
PAGES = {
    'SP500': ('List_of_S%26P_500_companies', 450, 550),
    'NASDAQ100': ('Nasdaq-100', 90, 125),
    'DOW30': ('Dow_Jones_Industrial_Average', 25, 35),
}
IWM_URL = ('https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/'
           '1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund')


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode('utf-8-sig', errors='replace')


def normalize(value):
    value = str(value).strip().upper().replace('.', '-')
    value = re.sub(r'\[.*?\]', '', value).strip()
    value = re.sub(r'^(?:NASDAQ|NYSE|NYSEARCA)\s*:\s*', '', value)
    return value if re.fullmatch(r'[A-Z][A-Z0-9-]{0,11}', value) else None


def flat_columns(frame):
    frame = frame.copy()
    frame.columns = [' '.join(str(v) for v in c if str(v) != 'nan') if isinstance(c, tuple) else str(c)
                     for c in frame.columns]
    return frame


def large_cap(index):
    entry = PAGES[index]
    slug, minimum, maximum = (entry[0], entry[-2], entry[-1])
    tables = pd.read_html(io.StringIO(download(WIKI + slug)))
    candidates = []
    for original in tables:
        table = flat_columns(original)
        for col in table.columns:
            label = str(col).lower().strip()
            if not re.search(r'\b(ticker|symbol)\b', label):
                continue
            values = list(dict.fromkeys(t for v in table[col].dropna() if (t := normalize(v))))
            if minimum <= len(values) <= maximum:
                candidates.append(values)
    if not candidates:
        raise RuntimeError(f'{index}: unable to identify constituent table (found {len(tables)} HTML tables)')
    return max(candidates, key=len)


def russell_proxy():
    content = download(os.getenv('IWM_HOLDINGS_URL', IWM_URL))
    lines = content.splitlines()
    header_index = None
    for i, line in enumerate(lines):
        try:
            fields = next(csv.reader([line]))
        except csv.Error:
            continue
        if fields and fields[0].strip().lstrip('\ufeff').strip('"').lower() == 'ticker' and len(fields) >= 3:
            header_index = i
            break
    if header_index is None:
        raise RuntimeError('IWM holdings response has no CSV Ticker header (provider may have changed format or blocked access)')
    frame = pd.read_csv(io.StringIO('\n'.join(lines[header_index:])), on_bad_lines='skip', low_memory=False)
    frame.columns = [str(c).strip().strip('"') for c in frame.columns]
    if 'Asset Class' in frame:
        frame = frame[frame['Asset Class'].astype(str).str.strip().str.lower() == 'equity']
    tickers = list(dict.fromkeys(t for v in frame['Ticker'].dropna() if (t := normalize(v))))
    if not 1500 <= len(tickers) <= 2500:
        raise RuntimeError(f'IWM proxy returned {len(tickers)} equity tickers, outside safety bounds')
    return tickers


def build_universe(indices):
    memberships, sources, failures = {}, {}, {}
    for index in indices:
        try:
            tickers = russell_proxy() if index == 'RUSSELL2000' else large_cap(index)
            sources[index] = ('IWM ETF holdings proxy; NOT official Russell index membership'
                              if index == 'RUSSELL2000' else 'Wikipedia constituent table')
            for ticker in tickers:
                memberships.setdefault(ticker, []).append(index)
        except Exception as exc:
            failures[index] = str(exc)
    if failures:
        raise RuntimeError(f'Universe source failures: {failures}')
    return {'as_of_utc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
            'memberships': memberships,
            'counts': {i: sum(i in v for v in memberships.values()) for i in indices}}
