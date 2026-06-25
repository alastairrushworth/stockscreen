"""
Daily data-fetch job for the static stock screener.

Pulls the current S&P 500 universe, downloads daily prices and per-ticker
fundamentals from Yahoo (via yfinance), computes a wide set of metrics, and
writes compact JSON files into ``data/`` for the static frontend to consume.

Outputs
-------
data/meta.json            run metadata (timestamp, counts, price window)
data/screen.json          one record per ticker with all current metrics
data/prices_monthly.json  month-end adjusted-close matrix for the backtest

Historical point-in-time fundamentals (data/fundamentals_history.json) are built
separately by build_history.py from SEC EDGAR. This job covers the live screener
(current Yahoo fundamentals) and the price history that powers all backtests.
"""

import json
import math
import os
import time
from datetime import date, datetime, timezone

import pandas as pd
import yfinance as yf

import config
from universe import get_universe


def log(*args):
    print(*args, flush=True)


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #
def download_prices(yahoo_tickers):
    """Download daily adjusted-close prices; return a DataFrame (cols=tickers)."""
    data = yf.download(
        yahoo_tickers,
        period=config.PRICE_PERIOD,
        interval="1d",
        auto_adjust=True,
        group_by="column",
        threads=True,
        progress=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:  # single ticker
        close = data[["Close"]].copy()
        close.columns = yahoo_tickers[:1]
    close = close.dropna(how="all")
    log(f"Prices: {close.shape[0]} rows x {close.shape[1]} tickers")
    return close


def _ret(series, start_ago, end_ago=0):
    """Return between the price ``start_ago`` rows back and ``end_ago`` rows back."""
    s = series.dropna()
    if len(s) <= start_ago:
        return None
    a = s.iloc[-1 - start_ago]
    b = s.iloc[-1 - end_ago]
    if a and a > 0 and b and b > 0:
        return float(b / a - 1.0)
    return None


def _ytd(series):
    s = series.dropna()
    if s.empty:
        return None
    yr = s.index[-1].year
    prev = s[s.index.year < yr]
    if prev.empty:
        return None
    base = prev.iloc[-1]
    if base and base > 0:
        return float(s.iloc[-1] / base - 1.0)
    return None


def _vol(series, days):
    """Annualised volatility of daily returns over the trailing ``days`` window."""
    s = series.dropna()
    if len(s) <= days:
        return None
    r = s.iloc[-days:].pct_change().dropna()
    if len(r) < 5:
        return None
    return float(r.std() * math.sqrt(252))


# Trading-day approximations.
M1, M3, M6, M12 = 21, 63, 126, 252


def price_metrics(series):
    """Current price-derived metrics for one ticker's close series."""
    return {
        "mom1": _ret(series, M1),
        "mom3": _ret(series, M3),
        "mom6": _ret(series, M6),
        "mom12_1": _ret(series, M12, M1),  # 12m return skipping the last month
        "retYtd": _ytd(series),
        "vol3m": _vol(series, M3),
        "vol12m": _vol(series, M12),
    }


# --------------------------------------------------------------------------- #
# Fundamentals
# --------------------------------------------------------------------------- #
def _num(info, key):
    v = info.get(key)
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _norm_yield(v):
    """Yahoo flip-flops between fraction (0.015) and percent (1.5) for yields."""
    if v is None:
        return None
    return v / 100.0 if v > 1 else v


def fetch_fundamentals(yahoo_tickers):
    """Return {yahoo_ticker: info_dict} with retries and throttling."""
    out = {}
    total = len(yahoo_tickers)
    for i, t in enumerate(yahoo_tickers):
        info = {}
        for attempt in range(config.MAX_RETRIES):
            try:
                got = yf.Ticker(t).info
                if got:
                    info = got
                    break
            except Exception as exc:  # noqa: BLE001 - tolerate any Yahoo hiccup
                if attempt == config.MAX_RETRIES - 1:
                    log(f"  ! {t}: {exc}")
                time.sleep(1 + attempt)
        out[t] = info
        time.sleep(config.REQUEST_SLEEP)
        if i % 50 == 0:
            log(f"  fundamentals {i}/{total}")
    return out


def fundamental_metrics(info):
    """Extract and normalise the fundamental metric set from a Yahoo info dict."""
    market_cap = _num(info, "marketCap")
    pe = _num(info, "trailingPE")
    fcf = _num(info, "freeCashflow")
    rec = {
        "marketCap": market_cap,
        "pe": pe,
        "forwardPe": _num(info, "forwardPE"),
        "pb": _num(info, "priceToBook"),
        "ps": _num(info, "priceToSalesTrailing12Months"),
        "evEbitda": _num(info, "enterpriseToEbitda"),
        "earningsYield": (1.0 / pe) if pe and pe > 0 else None,
        "fcfYield": (fcf / market_cap) if fcf and market_cap and market_cap > 0 else None,
        "roe": _num(info, "returnOnEquity"),
        "roa": _num(info, "returnOnAssets"),
        "grossMargin": _num(info, "grossMargins"),
        "operMargin": _num(info, "operatingMargins"),
        "netMargin": _num(info, "profitMargins"),
        "debtToEquity": _num(info, "debtToEquity"),
        "currentRatio": _num(info, "currentRatio"),
        "divYield": _norm_yield(_num(info, "dividendYield")),
        "payout": _num(info, "payoutRatio"),
        "beta": _num(info, "beta"),
        "revGrowth": _num(info, "revenueGrowth"),
        "earnGrowth": _num(info, "earningsGrowth"),
    }
    return rec


# --------------------------------------------------------------------------- #
# Assembly / output
# --------------------------------------------------------------------------- #
def build_monthly_matrix(close, yahoo_to_symbol):
    """Resample daily closes to month-end and emit a compact JSON-ready dict."""
    monthly = close.resample(config.MONTHLY_RULE).last().dropna(how="all")
    dates = [d.strftime("%Y-%m-%d") for d in monthly.index]
    series = {}
    for col in monthly.columns:
        sym = yahoo_to_symbol.get(col, col)
        vals = []
        for v in monthly[col].tolist():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                vals.append(None)
            else:
                vals.append(round(float(v), config.PRICE_DECIMALS))
        series[sym] = vals
    return {"dates": dates, "series": series}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, separators=(",", ":"), allow_nan=False)
    log(f"  wrote {path} ({os.path.getsize(path) // 1024} KB)")


def write_sitemap(last_modified):
    """Regenerate sitemap.xml so search engines see a fresh lastmod each run.

    The frontend is a single-page app (screener/backtest/about are tabs), so the
    sitemap lists the one canonical URL with the latest data date as lastmod.
    """
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{config.SITE_URL}</loc>\n"
        f"    <lastmod>{last_modified}</lastmod>\n"
        "    <changefreq>daily</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    with open("sitemap.xml", "w") as fh:
        fh.write(xml)
    log("  wrote sitemap.xml")


def main():
    today = date.today().isoformat()
    universe = get_universe()
    yahoo_tickers = universe["yahoo"].tolist()
    yahoo_to_symbol = dict(zip(universe["yahoo"], universe["symbol"]))

    close = download_prices(yahoo_tickers)

    log("Fetching fundamentals (this is the slow part)...")
    infos = fetch_fundamentals(yahoo_tickers)

    records = []
    for _, row in universe.iterrows():
        ytk, sym = row["yahoo"], row["symbol"]
        info = infos.get(ytk, {})
        fund = fundamental_metrics(info)

        last_price = None
        pm = {k: None for k in
              ("mom1", "mom3", "mom6", "mom12_1", "retYtd", "vol3m", "vol12m")}
        if ytk in close.columns:
            s = close[ytk].dropna()
            if not s.empty:
                last_price = round(float(s.iloc[-1]), 2)
                pm = price_metrics(s)

        rec = {"ticker": sym, "name": row["name"], "sector": row["sector"],
               "price": last_price, **fund, **pm}
        records.append(rec)

    with_price = sum(1 for r in records if r["price"] is not None)
    with_pe = sum(1 for r in records if r.get("pe") is not None)
    log(f"Built {len(records)} records ({with_price} priced, {with_pe} with P/E)")

    monthly = build_monthly_matrix(close, yahoo_to_symbol)

    meta = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "asOfDate": today,
        "universe": "S&P 500",
        "count": len(records),
        "priced": with_price,
        "priceStart": monthly["dates"][0] if monthly["dates"] else None,
        "priceEnd": monthly["dates"][-1] if monthly["dates"] else None,
        "source": "Yahoo Finance via yfinance",
        "sample": False,
    }

    write_json(os.path.join(config.DATA_DIR, "screen.json"), records)
    write_json(os.path.join(config.DATA_DIR, "prices_monthly.json"), monthly)
    write_json(os.path.join(config.DATA_DIR, "meta.json"), meta)
    write_sitemap(today)
    # Historical point-in-time fundamentals (fundamentals_history.json) are
    # built separately by build_history.py from SEC EDGAR.
    log("Done.")


if __name__ == "__main__":
    main()
