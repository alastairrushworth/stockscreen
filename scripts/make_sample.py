"""
Generate a small *synthetic* sample dataset so the static site works
immediately, before the first real GitHub Actions run.

Uses only the Python standard library (no yfinance / pandas) so it runs
anywhere. The daily job overwrites these files with real data. Everything it
writes is clearly marked ``"sample": true`` in meta.json.
"""

import json
import math
import os
import random
from datetime import date

import config

random.seed(42)

# A representative slice of large caps across sectors (names/sectors are real;
# all numbers below are synthetic).
SAMPLE = [
    ("AAPL", "Apple Inc.", "Information Technology"),
    ("MSFT", "Microsoft Corp.", "Information Technology"),
    ("NVDA", "NVIDIA Corp.", "Information Technology"),
    ("AVGO", "Broadcom Inc.", "Information Technology"),
    ("ORCL", "Oracle Corp.", "Information Technology"),
    ("CRM", "Salesforce Inc.", "Information Technology"),
    ("AMD", "Advanced Micro Devices", "Information Technology"),
    ("GOOGL", "Alphabet Inc.", "Communication Services"),
    ("META", "Meta Platforms Inc.", "Communication Services"),
    ("NFLX", "Netflix Inc.", "Communication Services"),
    ("DIS", "Walt Disney Co.", "Communication Services"),
    ("AMZN", "Amazon.com Inc.", "Consumer Discretionary"),
    ("TSLA", "Tesla Inc.", "Consumer Discretionary"),
    ("HD", "Home Depot Inc.", "Consumer Discretionary"),
    ("MCD", "McDonald's Corp.", "Consumer Discretionary"),
    ("NKE", "Nike Inc.", "Consumer Discretionary"),
    ("PG", "Procter & Gamble Co.", "Consumer Staples"),
    ("KO", "Coca-Cola Co.", "Consumer Staples"),
    ("PEP", "PepsiCo Inc.", "Consumer Staples"),
    ("WMT", "Walmart Inc.", "Consumer Staples"),
    ("COST", "Costco Wholesale", "Consumer Staples"),
    ("JPM", "JPMorgan Chase & Co.", "Financials"),
    ("BAC", "Bank of America Corp.", "Financials"),
    ("WFC", "Wells Fargo & Co.", "Financials"),
    ("GS", "Goldman Sachs Group", "Financials"),
    ("V", "Visa Inc.", "Financials"),
    ("MA", "Mastercard Inc.", "Financials"),
    ("BRK-B", "Berkshire Hathaway", "Financials"),
    ("UNH", "UnitedHealth Group", "Health Care"),
    ("JNJ", "Johnson & Johnson", "Health Care"),
    ("LLY", "Eli Lilly & Co.", "Health Care"),
    ("PFE", "Pfizer Inc.", "Health Care"),
    ("MRK", "Merck & Co.", "Health Care"),
    ("ABBV", "AbbVie Inc.", "Health Care"),
    ("XOM", "Exxon Mobil Corp.", "Energy"),
    ("CVX", "Chevron Corp.", "Energy"),
    ("COP", "ConocoPhillips", "Energy"),
    ("CAT", "Caterpillar Inc.", "Industrials"),
    ("BA", "Boeing Co.", "Industrials"),
    ("GE", "GE Aerospace", "Industrials"),
    ("HON", "Honeywell International", "Industrials"),
    ("LIN", "Linde plc", "Materials"),
    ("NEE", "NextEra Energy", "Utilities"),
    ("DUK", "Duke Energy Corp.", "Utilities"),
    ("AMT", "American Tower Corp.", "Real Estate"),
    ("PLD", "Prologis Inc.", "Real Estate"),
]

MONTHS = 120  # 10 years of month-end points


def month_ends(n):
    """Return ``n`` month-end ISO dates ending at the last full month."""
    y, m = 2016, 6
    out = []
    for _ in range(n):
        # last day of month (good enough: use 28 to avoid month-length logic)
        out.append(date(y, m, 28).isoformat())
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def random_walk(start, drift, vol):
    """A monthly geometric random walk of length MONTHS."""
    prices = [start]
    for _ in range(MONTHS - 1):
        shock = random.gauss(drift, vol)
        prices.append(round(prices[-1] * math.exp(shock), config.PRICE_DECIMALS))
    return prices


def pct(a, b):
    return (b / a - 1.0) if a and a > 0 else None


def main():
    dates = month_ends(MONTHS)
    series = {}
    records = []
    funds = {}

    for sym, name, sector in SAMPLE:
        start = random.uniform(20, 300)
        drift = random.uniform(-0.002, 0.015)   # monthly log-drift
        vol = random.uniform(0.03, 0.11)        # monthly log-vol
        prices = random_walk(start, drift, vol)
        series[sym] = prices

        # Price-derived current metrics, computed from the monthly series so the
        # screener and backtest are mutually consistent in the sample.
        rets = [pct(prices[i - 1], prices[i]) for i in range(1, len(prices))]
        last12 = rets[-12:]
        mean12 = sum(last12) / len(last12)
        var12 = sum((r - mean12) ** 2 for r in last12) / len(last12)
        vol12 = math.sqrt(var12) * math.sqrt(12)

        pe = round(random.uniform(8, 45), 1)
        roe = round(random.uniform(0.02, 0.45), 3)
        fund = {
            "marketCap": round(start * random.uniform(1e8, 3e9)),
            "pe": pe,
            "forwardPe": round(pe * random.uniform(0.8, 1.1), 1),
            "pb": round(random.uniform(1, 18), 2),
            "ps": round(random.uniform(0.5, 14), 2),
            "evEbitda": round(random.uniform(6, 30), 1),
            "earningsYield": round(1.0 / pe, 4),
            "fcfYield": round(random.uniform(0.005, 0.09), 4),
            "roe": roe,
            "roa": round(roe * random.uniform(0.2, 0.6), 3),
            "grossMargin": round(random.uniform(0.2, 0.7), 3),
            "operMargin": round(random.uniform(0.05, 0.4), 3),
            "netMargin": round(random.uniform(0.03, 0.3), 3),
            "debtToEquity": round(random.uniform(10, 220), 1),
            "currentRatio": round(random.uniform(0.8, 3.5), 2),
            "divYield": round(random.uniform(0, 0.045), 4),
            "payout": round(random.uniform(0, 0.7), 3),
            "beta": round(random.uniform(0.5, 1.8), 2),
            "revGrowth": round(random.uniform(-0.1, 0.4), 3),
            "earnGrowth": round(random.uniform(-0.2, 0.5), 3),
        }
        price_metrics = {
            "mom1": round(rets[-1], 4),
            "mom3": round(pct(prices[-4], prices[-1]), 4),
            "mom6": round(pct(prices[-7], prices[-1]), 4),
            "mom12_1": round(pct(prices[-13], prices[-2]), 4),
            "retYtd": round(pct(prices[-7], prices[-1]), 4),
            "vol3m": round(vol12 * random.uniform(0.8, 1.2), 4),
            "vol12m": round(vol12, 4),
        }
        records.append({"ticker": sym, "name": name, "sector": sector,
                        "price": prices[-1], **fund, **price_metrics})
        funds[sym] = fund

    # Build a synthetic *point-in-time* fundamentals history in the SAME schema
    # the real SEC job produces: per ticker, a list of [filing_date, raw items]
    # entries. Raw TTM/balance items are derived from the latest fundamentals
    # and grown backwards through time; the browser turns them into ratios using
    # the monthly price matrix. (The real history comes from build_history.py.)
    OUTPUT_FIELDS = ["ni", "rev", "gp", "oi", "cfo", "capex", "div",
                     "eq", "assets", "debt", "sh"]

    def base_raw(sym):
        f = funds[sym]
        mc = f["marketCap"]
        px_last = series[sym][-1]
        sh = mc / px_last
        ni = mc * f["earningsYield"]
        eq = mc / f["pb"]
        rev = mc / f["ps"]
        assets = ni / f["roa"] if f["roa"] > 0 else eq * 2.2
        fcf = f["fcfYield"] * mc
        capex = abs(fcf) * 0.5 + mc * 0.005
        return {
            "ni": ni, "rev": rev,
            "gp": f["grossMargin"] * rev, "oi": f["operMargin"] * rev,
            "cfo": fcf + capex, "capex": capex, "div": f["divYield"] * mc,
            "eq": eq, "assets": assets,
            "debt": (f["debtToEquity"] / 100.0) * eq, "sh": sh,
        }

    def rnd(v):
        return round(v, 4) if abs(v) < 1000 else round(v)

    history_tickers = {}
    for sym, _, _ in SAMPLE:
        base = base_raw(sym)
        g = random.uniform(1.02, 1.18)        # annual growth of the business
        entries = []
        for m in range(3, MONTHS, 3):         # quarterly filings
            scale = g ** ((m - (MONTHS - 1)) / 12.0)   # <1 in the past
            flow_scale = scale
            obj = {}
            for k in ("ni", "rev", "gp", "oi", "cfo", "capex", "div"):
                obj[k] = rnd(base[k] * flow_scale)
            for k in ("eq", "assets", "debt"):
                obj[k] = rnd(base[k] * scale)
            obj["sh"] = rnd(base["sh"])       # shares roughly constant
            entries.append([dates[m], obj])
        history_tickers[sym] = entries

    history = {
        "asOf": dates[-1],
        "fields": OUTPUT_FIELDS,
        "source": "synthetic sample (point-in-time)",
        "tickers": history_tickers,
    }

    meta = {
        "updated": "sample data — run the daily job for real data",
        "asOfDate": dates[-1],
        "universe": "S&P 500 (sample subset)",
        "count": len(records),
        "priced": len(records),
        "priceStart": dates[0],
        "priceEnd": dates[-1],
        "source": "synthetic sample",
        "sample": True,
    }

    os.makedirs(config.DATA_DIR, exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(config.DATA_DIR, name), "w") as fh:
            json.dump(obj, fh, separators=(",", ":"))

    dump("screen.json", records)
    dump("prices_monthly.json", {"dates": dates, "series": series})
    dump("meta.json", meta)
    dump("fundamentals_history.json", history)
    n_entries = sum(len(v) for v in history_tickers.values())
    print(f"Wrote sample data for {len(records)} tickers, {MONTHS} months, "
          f"{n_entries} point-in-time fundamental entries.")


if __name__ == "__main__":
    main()
