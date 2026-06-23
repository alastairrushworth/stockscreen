# Stock Screener & Factor Backtester

A **fully static** stock-screening and long/short factor-backtesting web app for
the S&P 500. A **daily** GitHub Actions job refreshes prices and current
fundamentals; a **weekly** job rebuilds ~15 years of **point-in-time
fundamentals from SEC EDGAR**. Everything is committed as compact JSON and the
browser does all ranking and backtesting client-side — no server or database.

![screener](https://img.shields.io/badge/hosting-GitHub%20Pages-blue) ![data](https://img.shields.io/badge/data-Yahoo%20%2B%20SEC%20EDGAR-orange)

## Features

- **Screener** — rank the S&P 500 by a composite z-score across valuation,
  quality, momentum, risk and growth metrics. Presets (Value, Quality,
  Momentum, Low-Vol, Dividend, Multi-Factor) or toggle individual metrics.
  Sort any column, filter by sector / market cap, export to CSV.
- **Backtest** — equal-weighted long/short quantile portfolios over price
  factors (momentum, low-vol, reversal) **and point-in-time fundamental
  factors** (E/P, B/P, S/P, FCF & dividend yield, ROE/ROA, margins, debt) with
  CAGR, volatility, Sharpe, max drawdown and hit rate vs an equal-weight
  benchmark, plotted as an interactive equity curve.
- **Auto-update** — daily prices (`update-data.yml`) + weekly SEC fundamentals
  (`update-fundamentals.yml`), both committed back to the repo.

## How it works

```
GitHub Actions                                 GitHub Pages (static)
┌──────────────────────────────────┐           ┌──────────────────────────┐
│ daily:  fetch_data.py             │  commits  │ index.html + js/ + css/   │
│   • S&P 500 list (Wikipedia)      │ ────────► │  • fetch() data/*.json    │
│   • 15y prices + fundamentals     │ data/     │  • screen + backtest      │
│     (yfinance / Yahoo)            │  *.json   │    entirely in the browser │
│ weekly: build_history.py          │           │                          │
│   • point-in-time fundamentals    │           │                          │
│     (SEC EDGAR companyfacts)      │           │                          │
└──────────────────────────────────┘           └──────────────────────────┘
```

### Data files (`data/`)

| File | Contents |
|------|----------|
| `meta.json` | Run timestamp, universe size, price window, source flag |
| `screen.json` | One record per ticker with all current metrics (Yahoo) |
| `prices_monthly.json` | Month-end adjusted-close matrix (powers the backtest) |
| `fundamentals_history.json` | Point-in-time SEC fundamentals: `{ticker: [[filing_date, {raw TTM & balance-sheet items}], …]}`. The browser turns raw items into ratios using monthly prices. |

### Point-in-time fundamentals

`scripts/sec.py` reads SEC EDGAR `companyfacts`, where every figure carries the
date it was **filed**. For each quarter it rolls four quarters into a TTM value
(deriving the missing Q4 as `annual − (Q1+Q2+Q3)`) and pairs it with the latest
already-filed balance-sheet instants. Backtests at month *t* use only entries
filed on or before *t*, so there is **no look-ahead bias**.

## Setup

### 1. Run it locally

The repo ships with **synthetic sample data** so the site works immediately.
Serve over HTTP (browsers block `fetch` from `file://`):

```bash
python -m http.server 8000
# open http://localhost:8000
```

To regenerate the sample data: `python scripts/make_sample.py`.

### 2. Get real data

```bash
pip install -r scripts/requirements.txt

# Daily data: ~15y prices + current fundamentals (~5–15 min for 500 tickers)
python scripts/fetch_data.py

# Historical point-in-time fundamentals from SEC EDGAR (~5–20 min; cached)
export SEC_USER_AGENT="your-app-name your-email@example.com"   # SEC asks for this
python scripts/build_history.py
```

`fetch_data.py` writes `screen.json`, `prices_monthly.json`, `meta.json`;
`build_history.py` writes `fundamentals_history.json`. SEC responses are cached
under `.cache/sec/` (gitignored) so reruns are fast.

### 3. Deploy on GitHub Pages

1. Push to GitHub.
2. **Settings → Pages → Build and deployment → Deploy from a branch**, choose
   `main` / `/ (root)`.
3. **Settings → Actions → General → Workflow permissions → Read and write** so
   the jobs can commit data.
4. Trigger first runs from **Actions** → run **Update data** and **Update
   fundamentals history**.

The weekly fundamentals job sets a default `SEC_USER_AGENT`; override it with a
real contact via a repo variable/secret if you like.

The site goes live at `https://<you>.github.io/<repo>/`, with prices refreshing
daily and fundamentals weekly.

## Important limitations

- **Point-in-time integrity.** Historical fundamentals are keyed by SEC filing
  date, so backtests don't use figures that weren't public yet. TTM
  reconstruction derives the missing Q4 as `annual − (Q1+Q2+Q3)`; sparse or
  non-standard XBRL tagging means some company/metric combinations are skipped.
- **Survivorship bias.** The universe is the *current* S&P 500, so delisted
  names are absent from historical tests.
- **Screener vs backtest source.** The live screener uses Yahoo's *current*
  fundamentals; the backtest uses SEC point-in-time data — the two can differ
  slightly for the latest period.
- **Gross of costs.** No trading costs, slippage, borrow fees or taxes.
- **Unofficial price data.** Yahoo prices can have gaps/errors; missing values
  are excluded from ranking.

> Not investment advice. For research and education only.

## Customising

- **Universe** — edit `get_universe()` in `scripts/universe.py` (e.g. read a
  `tickers.txt`, or switch to the S&P 400/600 Wikipedia tables).
- **History depth / payload** — `PRICE_PERIOD`, `PRICE_DECIMALS`, `HISTORY_START`
  in `scripts/config.py`.
- **Metrics, presets, factors** — `js/metrics.js`.

## Project layout

```
index.html                  # UI shell (Screener / Backtest / About tabs)
css/style.css
js/util.js                  # stats + formatting helpers
js/metrics.js               # metric, preset & factor registries
js/chart.js                 # dependency-free canvas line chart
js/screener.js              # composite scoring + ranking table
js/backtest.js              # long/short quantile backtest engine
js/app.js                   # data loading + tab wiring
scripts/universe.py         # shared S&P 500 list loader
scripts/fetch_data.py       # daily prices + current fundamentals (yfinance)
scripts/sec.py              # SEC EDGAR point-in-time fundamentals extraction
scripts/build_history.py    # builds fundamentals_history.json from SEC
scripts/make_sample.py      # synthetic sample-data generator
scripts/config.py
.github/workflows/update-data.yml          # daily
.github/workflows/update-fundamentals.yml  # weekly
data/                       # generated JSON (committed by the jobs)
```
