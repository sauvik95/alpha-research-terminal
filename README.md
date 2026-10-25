# Alpha Research Terminal — zero-paid-API prototype

A transparent, **rule-based** US stock screening dashboard with three independent scoring modules (fundamental, technical, quantitative), a committee aggregation step, and daily dated JSON snapshots. It is **not yet a team of LLM agents** and does not provide real agent-to-agent debate, audited SEC fundamentals, forecasts, alerts, Supabase synchronization, or an automated 11 PM ChatGPT report. Those are separate later integrations.

## Quick start (computer, optional)

```bash
pip install -r requirements.txt
python research.py
streamlit run app.py
```

## Python deployment

1. In the iPhone **Files** app, tap the downloaded ZIP to extract it.
2. Open https://github.com/sauvik95/alpha-research-terminal in Safari. If the repo is empty, create a README via GitHub first so its file upload interface becomes available. Use **Add file → Upload files**. GitHub's mobile web upload may not preserve folder trees; the most reliable route is Safari **Request Desktop Website** and uploading the extracted folder contents in batches, checking that `agents/scoring.py` and `.github/workflows/research.yml` retain their paths. If the upload UI won't preserve folders, create the folders and files using GitHub's **Create new file** and slash-separated paths, or use a computer once.
3. In the repository, open **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions** only if the workflow cannot commit snapshots. Do not enable paid services or add billing information.
4. Go to **Actions → Update stock research → Run workflow**. Wait for completion, then verify `data/latest.json` appears in your repository.
5. Open https://share.streamlit.io/ and deploy a **new app** from your GitHub repo, branch `main`, entrypoint `app.py`. Community Cloud free-tier availability and resource limits are subject to change.
6. GitHub Actions scheduled jobs run on **UTC** and may be delayed; the included schedule is approximate and will not always align with 11 PM ET because of daylight saving time.

**If your upload creates a nested `alpha-research-terminal/` directory:** move files to the repo root or configure Streamlit's entrypoint accordingly. `app.py`, `research.py`, `requirements.txt` must be at the root for the default instructions.

## Data and decisions

- Prices and basic company fields: `yfinance` (unofficial Yahoo Finance access; subject to outages, rate limits and terms).
- Fundamental: revenue growth, earnings growth, ROE, forward P/E, debt/equity where available. Missing inputs are not silently assigned perfect scores.
- Technical: moving averages and momentum.
- Quantitative: historical beta, approximate alpha, volatility, drawdown and momentum.
- Committee: weighted scores (40% fundamental, 25% technical, 35% quant), and explicit disagreement flag.
- The `data/YYYY-MM-DD.json` files preserve daily snapshots in Git history. The dashboard charts historical conviction as files accumulate.
- **No score is a probability of winning or a 1–3 year price target.** The watchlist is a demonstration universe, not a validated shortlist of high-upside investments.

## Cost and privacy

No paid APIs or credentials are required. Public GitHub repositories and Streamlit Community Cloud may have free usage subject to provider policies; verify account billing settings and usage limits yourself. The repo is public: do **not** commit private investment records, keys, passwords, brokerage information or Supabase service-role credentials.

## Troubleshooting

- **403 when workflow pushes:** Check Actions workflow permissions and branch protection rules. The ChatGPT GitHub connector's 403 is separate and does not prevent manual uploads.
- **Empty dashboard:** Manually run the workflow first; ensure `data/latest.json` was committed.
- **Yahoo errors:** Retry later; the script preserves the prior snapshot if every ticker fails.
- **Missing fundamentals:** Some symbols have sparse or unreliable Yahoo metadata; the dashboard reports coverage.
- **Schedule not firing:** GitHub may delay scheduled runs or disable schedules on inactive repositories; use manual Run workflow.
