# Alpha Research Terminal — zero-paid-API prototype

A transparent, **rule-based** US stock screening dashboard with three independent scoring modules (fundamental, technical, quantitative), a committee aggregation step, and daily dated JSON snapshots. It is **not yet a team of LLM agents** and does not provide real agent-to-agent debate, audited SEC fundamentals, forecasts, alerts, Supabase synchronization, or an automated 11 PM ChatGPT report. Those are separate later integrations.


## Data and decisions

- Prices and basic company fields: `yfinance` (unofficial Yahoo Finance access; subject to outages, rate limits and terms).
- Fundamental: revenue growth, earnings growth, ROE, forward P/E, debt/equity where available. Missing inputs are not silently assigned perfect scores.
- Technical: moving averages and momentum.
- Quantitative: historical beta, approximate alpha, volatility, drawdown and momentum.
- Committee: weighted scores (40% fundamental, 25% technical, 35% quant), and explicit disagreement flag.
- The `data/YYYY-MM-DD.json` files preserve daily snapshots in Git history. The dashboard charts historical conviction as files accumulate.
- **No score is a probability of winning or a 1–3 year price target.** The watchlist is a demonstration universe, not a validated shortlist of high-upside investments.


## Troubleshooting

- **403 when workflow pushes:** Check Actions workflow permissions and branch protection rules. The ChatGPT GitHub connector's 403 is separate and does not prevent manual uploads.
- **Empty dashboard:** Manually run the workflow first; ensure `data/latest.json` was committed.
- **Yahoo errors:** Retry later; the script preserves the prior snapshot if every ticker fails.
- **Missing fundamentals:** Some symbols have sparse or unreliable Yahoo metadata; the dashboard reports coverage.
- **Schedule not firing:** GitHub may delay scheduled runs or disable schedules on inactive repositories; use manual Run workflow.
