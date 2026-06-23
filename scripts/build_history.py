"""
Build data/fundamentals_history.json — point-in-time historical fundamentals
for the S&P 500 from SEC EDGAR, used by the fundamental-factor backtest.

Output schema:
{
  "asOf": "2026-06-23",
  "fields": ["ni","rev","gp","oi","cfo","capex","div","eq","assets","debt","sh"],
  "tickers": {
     "AAPL": [ ["2018-02-02", { "ni": ..., "rev": ..., ... }], ... ],   # sorted
     ...
  }
}

Each entry is [filing_date, raw TTM/balance-sheet items]. The browser computes
valuation ratios (E/P, B/P, FCF yield, …) from these against the monthly price
matrix, so valuation updates monthly without inflating this file.
"""

import json
import os
from datetime import date

import config
import sec
from universe import get_universe


def log(*a):
    print(*a, flush=True)


def main():
    universe = get_universe()
    log(f"Universe: {len(universe)} tickers")

    session = sec._session()
    log("Fetching SEC ticker→CIK map...")
    cik_map = sec.get_cik_map(session)

    out = {}
    n_ok = n_nocik = n_nodata = 0
    total = len(universe)
    for i, row in enumerate(universe.itertuples(index=False)):
        sym, ytk = row.symbol, row.yahoo
        cik = cik_map.get(ytk.upper()) or cik_map.get(sym.upper())
        if cik is None:
            n_nocik += 1
            continue
        facts = sec.get_company_facts(session, cik)
        if not facts:
            n_nodata += 1
            continue
        try:
            entries = sec.build_entries(facts, min_filed=config.HISTORY_START)
        except Exception as exc:  # noqa: BLE001 - tolerate odd filings
            log(f"  ! {sym}: parse error {exc}")
            entries = []
        if entries:
            out[sym] = entries
            n_ok += 1
        if i % 50 == 0:
            log(f"  {i}/{total}  (ok={n_ok}, no-cik={n_nocik}, no-data={n_nodata})")

    payload = {
        "asOf": date.today().isoformat(),
        "fields": sec.OUTPUT_FIELDS,
        "source": "SEC EDGAR companyfacts (point-in-time)",
        "tickers": out,
    }
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, "fundamentals_history.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))

    n_entries = sum(len(v) for v in out.values())
    size_kb = os.path.getsize(path) // 1024
    log(f"Wrote {path}: {n_ok} tickers, {n_entries} entries, {size_kb} KB "
        f"(no-cik={n_nocik}, no-data={n_nodata})")


if __name__ == "__main__":
    main()
