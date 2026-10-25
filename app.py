"""Multi-index Streamlit explorer; reads committed GitHub snapshots."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Alpha Research Terminal', page_icon='📈', layout='wide')
st.title('📈 Alpha Research Terminal')
path = Path(__file__).parent / 'data/latest.json'
if not path.exists():
    st.info('Run the GitHub Actions workflow to generate data/latest.json')
    st.stop()
d = json.loads(path.read_text())
results = d.get('results', [])
st.caption(f'Snapshot: {d.get("generated_at_utc", "unknown")} · Benchmark: SPY · Historical heuristic screening, not investment advice')
if not results:
    st.warning('No scored stocks available')
    st.stop()

rows = []
for r in results:
    a = r['agents']
    rows.append({'Ticker': r['ticker'], 'Company': r['company'], 'Indices': ', '.join(r.get('indices', [])),
                 'Price': r['price'], 'Committee': r['committee']['score'],
                 'Decision': r['committee']['decision'], 'Fundamental': a['fundamental']['score'],
                 'Technical': a['technical']['score'], 'Quantitative': a['quantitative']['score'],
                 'Disagreement': r['committee']['disagreement'],
                 'Price date': r['as_of_price_date']})
df = pd.DataFrame(rows)
c1, c2, c3 = st.columns(3)
c1.metric('Unique stocks analyzed', len(df))
c2.metric('Price coverage', f'{d.get("price_coverage", 0):.1%}')
c3.metric('Fundamental profiles cached', d.get('fundamentals_refresh', {}).get('cached_profiles', 0))
indices = sorted(set(x for r in results for x in r.get('indices', [])))
selected = st.multiselect('Filter by index', indices, default=indices)
min_score = st.slider('Minimum committee score', 0, 100, 0)
search = st.text_input('Find a ticker or company')
filtered = df[df['Indices'].apply(lambda x: any(i in x.split(', ') for i in selected))]
filtered = filtered[filtered['Committee'].fillna(-1) >= min_score]
if search:
    filtered = filtered[filtered['Ticker'].str.contains(search, case=False, regex=False) |
                        filtered['Company'].str.contains(search, case=False, regex=False)]
filtered = filtered.sort_values('Committee', ascending=False, na_position='last')
st.dataframe(filtered, hide_index=True, use_container_width=True, height=520)
if not filtered.empty:
    ticker = st.selectbox('Detailed research', filtered['Ticker'].tolist())
    r = next(r for r in results if r['ticker'] == ticker)
    st.subheader(f'{r["company"]} ({ticker})')
    st.write(f'**Committee:** {r["committee"]["score"]}/100 · {r["committee"]["decision"]}')
    st.caption('Index membership: ' + ', '.join(r.get('indices', [])))
    for name, agent in r['agents'].items():
        with st.expander(f'{name.title()} · {agent.get("score")} / 100'):
            st.json(agent)
    st.write('**Rule-based committee discussion:**')
    for line in r['committee']['debate']:
        st.write('• ' + line)
with st.expander('Data quality / source notes'):
    st.json({'index_sources': d.get('index_sources'), 'index_counts': d.get('index_counts'),
             'fundamental_refresh': d.get('fundamentals_refresh'),
             'price_errors': d.get('price_errors'), 'fundamental_errors': d.get('fundamental_errors')})
st.warning('Russell 2000 uses IWM ETF holdings as a proxy, not official FTSE Russell membership. Scores are not forecasts.')
