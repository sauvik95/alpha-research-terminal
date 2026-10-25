"""Free Streamlit research terminal, powered by GitHub snapshots."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Alpha Research Terminal',page_icon='📈',layout='wide')
st.title('📈 Alpha Research Terminal')
st.caption('Fundamental • Technical • Quantitative • Investment committee')
p=Path(__file__).parent/'data/latest.json'
if not p.exists():
    st.info('No research snapshot yet. Run `python research.py` or the GitHub Actions workflow.')
    st.stop()
try: d=json.loads(p.read_text())
except Exception as e: st.error(f'Unable to load snapshot: {e}'); st.stop()
st.caption(f'Last generated (UTC): {d.get("generated_at_utc","unknown")} · Benchmark: {d.get("benchmark","SPY")}')
rows=[]
for r in d.get('results',[]):
    rows.append({'Ticker':r['ticker'],'Company':r['company'],'Price':r['price'],
                 'Committee':r['committee']['score'],'Decision':r['committee']['decision'],
                 'Fundamental':r['agents']['fundamental']['score'],
                 'Technical':r['agents']['technical']['score'],
                 'Quantitative':r['agents']['quantitative']['score'],
                 'Disagreement':r['committee']['disagreement']})
if not rows: st.warning('Snapshot contains no stocks.'); st.stop()
df=pd.DataFrame(rows)
st.dataframe(df,use_container_width=True,hide_index=True)
ticker=st.selectbox('Inspect stock',df['Ticker'].tolist())
r=next(x for x in d['results'] if x['ticker']==ticker)
st.subheader(f'{r["company"]} ({ticker})')
st.write(f'**Committee:** {r["committee"]["decision"]} · **Score:** {r["committee"]["score"]}/100')
st.write('**Committee discussion (rule-based):**')
for line in r['committee']['debate']: st.write('• '+line)
for name,agent in r['agents'].items():
    with st.expander(f'{name.title()} agent — {agent.get("score")} / 100'):
        st.json(agent)
st.divider()
st.subheader('Historical conviction')
history=[]
for f in sorted((Path(__file__).parent/'data').glob('20??-??-??.json')):
    try:
        h=json.loads(f.read_text()); hit=next((x for x in h.get('results',[]) if x['ticker']==ticker),None)
        if hit: history.append({'date':f.stem,'score':hit['committee']['score'],'price':hit['price'],'decision':hit['committee']['decision']})
    except Exception: pass
if history:
    hdf=pd.DataFrame(history).set_index('date')
    st.line_chart(hdf[['score']]); st.dataframe(hdf,use_container_width=True)
else: st.caption('History will build as daily snapshots are committed.')
if d.get('errors'):
    with st.expander('Data collection errors'): st.json(d['errors'])
st.warning('Experimental research screener, not autonomous AI analysts or financial advice. Scores are heuristic rankings, not probabilities of upside. Data may be stale.')
