"""
SEC EDGAR helpers for building *point-in-time* historical fundamentals.

The EDGAR ``companyfacts`` API exposes every XBRL fact a company has filed,
each tagged with the date it was ``filed``. That filing date is what makes the
data point-in-time: at any historical month we only use facts that had already
been filed by then, so backtests don't peek at figures that weren't public yet.

For each company we reconstruct a quarterly series of flow items (net income,
revenue, …) — deriving the missing Q4 as ``annual − (Q1+Q2+Q3)`` — roll them
into trailing-twelve-month (TTM) figures, and pair them with the latest
balance-sheet instants (equity, assets, debt, shares). The output is a list of
``[filing_date, {raw items}]`` entries per ticker; the browser turns those raw
items into valuation/quality ratios using the monthly price matrix.
"""

import json
import os
import time
from datetime import datetime

import requests

import config

# Candidate XBRL concept names per logical item (tried in order; companies tag
# the same idea differently). taxonomy:name.
FLOW_CONCEPTS = {
    "ni":    ("us-gaap", ["NetIncomeLoss",
                          "NetIncomeLossAvailableToCommonStockholdersBasic"]),
    "rev":   ("us-gaap", ["RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Revenues", "SalesRevenueNet",
                          "RevenueFromContractWithCustomerIncludingAssessedTax"]),
    "gp":    ("us-gaap", ["GrossProfit"]),
    "oi":    ("us-gaap", ["OperatingIncomeLoss"]),
    "cfo":   ("us-gaap", ["NetCashProvidedByUsedInOperatingActivities",
                          "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    "capex": ("us-gaap", ["PaymentsToAcquirePropertyPlantAndEquipment",
                          "PaymentsToAcquireProductiveAssets"]),
    "div":   ("us-gaap", ["PaymentsOfDividendsCommon", "PaymentsOfDividends",
                          "DividendsCommonStock"]),
}

INSTANT_CONCEPTS = {
    "eq":     ("us-gaap", ["StockholdersEquity",
                          "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
    "assets": ("us-gaap", ["Assets"]),
    "cash":   ("us-gaap", ["CashAndCashEquivalentsAtCarryingValue",
                          "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]),
    "debt_lt": ("us-gaap", ["LongTermDebtNoncurrent", "LongTermDebt"]),
    "debt_cur": ("us-gaap", ["LongTermDebtCurrent", "DebtCurrent"]),
    "sh":     ("dei", ["EntityCommonStockSharesOutstanding"]),
    "sh_gaap": ("us-gaap", ["CommonStockSharesOutstanding"]),
}

OUTPUT_FIELDS = ["ni", "rev", "gp", "oi", "cfo", "capex", "div",
                 "eq", "assets", "debt", "sh"]


def log(*a):
    print(*a, flush=True)


def _days(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": config.SEC_USER_AGENT,
                      "Accept-Encoding": "gzip, deflate"})
    return s


def get_cik_map(session):
    """Return {TICKER: zero-padded-CIK-int} from SEC's ticker file."""
    r = session.get(config.SEC_TICKERS_URL, timeout=30)
    r.raise_for_status()
    out = {}
    for row in r.json().values():
        out[row["ticker"].upper()] = int(row["cik_str"])
    return out


def get_company_facts(session, cik):
    """Fetch (and disk-cache) a company's XBRL facts JSON. None on failure."""
    os.makedirs(config.SEC_CACHE_DIR, exist_ok=True)
    cache = os.path.join(config.SEC_CACHE_DIR, f"CIK{cik:010d}.json")
    if os.path.exists(cache):
        try:
            with open(cache) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    url = config.SEC_FACTS_URL.format(cik=cik)
    for attempt in range(config.SEC_MAX_RETRIES):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            with open(cache, "w") as fh:
                json.dump(data, fh)
            time.sleep(config.SEC_SLEEP)
            return data
        except Exception as exc:  # noqa: BLE001
            if attempt == config.SEC_MAX_RETRIES - 1:
                log(f"  ! facts CIK{cik}: {exc}")
                return None
            time.sleep(1 + attempt)
    return None


# --------------------------------------------------------------------------- #
# Fact extraction
# --------------------------------------------------------------------------- #
def _concept_units(facts, taxonomy, names):
    """Return the first matching concept's unit->facts dict, or {}."""
    node = facts.get("facts", {}).get(taxonomy, {})
    for n in names:
        if n in node:
            return node[n].get("units", {})
    return {}


def _usd_facts(facts, taxonomy, names):
    units = _concept_units(facts, taxonomy, names)
    return units.get("USD", [])


def _share_facts(facts, taxonomy, names):
    units = _concept_units(facts, taxonomy, names)
    return units.get("shares", [])


def quarterly_series(usd_facts):
    """Reconstruct a sorted quarterly series [(qend, val, filed), ...].

    Keeps the latest-filed value per (start, end) period, classifies periods as
    quarterly (~3 mo) or annual (~12 mo), and synthesises the missing Q4 from
    the annual figure minus the three reported quarters.
    """
    best = {}
    for f in usd_facts:
        s, e, filed = f.get("start"), f.get("end"), f.get("filed")
        if not s or not e or filed is None or f.get("val") is None:
            continue
        key = (s, e)
        if key not in best or filed > best[key].get("filed", ""):
            best[key] = f

    quarters = {}   # end -> {val, filed}
    annuals = []     # list of {start, end, val, filed}
    for (s, e), f in best.items():
        d = _days(s, e)
        if 80 <= d <= 100:
            quarters[e] = {"val": f["val"], "filed": f["filed"]}
        elif 350 <= d <= 380:
            annuals.append({"start": s, "end": e, "val": f["val"], "filed": f["filed"]})

    for a in annuals:
        if a["end"] in quarters:
            continue
        inner = sorted(qe for qe in quarters if a["start"] < qe < a["end"])
        if len(inner) >= 3:
            three = inner[-3:]
            ssum = sum(quarters[qe]["val"] for qe in three)
            filed = max([a["filed"]] + [quarters[qe]["filed"] for qe in three])
            quarters[a["end"]] = {"val": a["val"] - ssum, "filed": filed}

    return sorted((e, quarters[e]["val"], quarters[e]["filed"]) for e in quarters)


def ttm_points(usd_facts):
    """Trailing-12-month points: {qend: {val, filed}} from 4 rolling quarters."""
    q = quarterly_series(usd_facts)
    out = {}
    for k in range(3, len(q)):
        window = q[k - 3:k + 1]
        # require the four quarter-ends to span ~1 year (guards against gaps)
        if _days(window[0][0], window[3][0]) > 290:
            continue
        out[q[k][0]] = {
            "val": sum(w[1] for w in window),
            "filed": max(w[2] for w in window),
        }
    return out


def instant_series(usd_or_share_facts):
    """Sorted [(end, val, filed)] keeping the latest-filed value per end date."""
    best = {}
    for f in usd_or_share_facts:
        e, filed = f.get("end"), f.get("filed")
        if not e or filed is None or f.get("val") is None:
            continue
        if e not in best or filed > best[e].get("filed", ""):
            best[e] = {"val": f["val"], "filed": filed}
    return sorted((e, best[e]["val"], best[e]["filed"]) for e in best)


def _latest_on_or_before(series, end_limit, filed_limit):
    """Latest (end<=end_limit, filed<=filed_limit) value from an instant series."""
    chosen = None
    for end, val, filed in series:
        if end <= end_limit and filed <= filed_limit:
            if chosen is None or end > chosen[0]:
                chosen = (end, val)
    return chosen[1] if chosen else None


# --------------------------------------------------------------------------- #
# Per-company assembly
# --------------------------------------------------------------------------- #
def build_entries(facts, min_filed=None):
    """Build point-in-time [filed_date, {raw items}] entries for one company."""
    flows = {k: ttm_points(_usd_facts(facts, tax, names))
             for k, (tax, names) in FLOW_CONCEPTS.items()}

    instants = {}
    for k, (tax, names) in INSTANT_CONCEPTS.items():
        getter = _share_facts if tax == "dei" or k.startswith("sh") else _usd_facts
        instants[k] = instant_series(getter(facts, tax, names))

    # Net income drives the backbone of quarter-end dates.
    ni = flows["ni"]
    entries = []
    for qend in sorted(ni):
        filed = ni[qend]["filed"]
        if min_filed and filed < min_filed:
            continue

        obj = {"ni": ni[qend]["val"]}
        for k in ("rev", "gp", "oi", "cfo", "capex", "div"):
            pt = flows[k].get(qend)
            if pt is not None and pt["filed"] <= filed:
                obj[k] = pt["val"]

        # Balance-sheet instants as of this quarter end, only if already filed.
        eq = _latest_on_or_before(instants["eq"], qend, filed)
        assets = _latest_on_or_before(instants["assets"], qend, filed)
        debt_lt = _latest_on_or_before(instants["debt_lt"], qend, filed) or 0.0
        debt_cur = _latest_on_or_before(instants["debt_cur"], qend, filed) or 0.0
        debt = debt_lt + debt_cur
        # Shares: prefer dei cover-page count filed by this date.
        sh = (_latest_on_or_before(instants["sh"], filed, filed)
              or _latest_on_or_before(instants["sh_gaap"], qend, filed))

        if eq is not None:
            obj["eq"] = eq
        if assets is not None:
            obj["assets"] = assets
        if debt:
            obj["debt"] = debt
        if sh:
            obj["sh"] = sh

        # dividends/capex are reported as positive cash outflows; keep absolute.
        for k in ("div", "capex"):
            if k in obj and obj[k] is not None:
                obj[k] = abs(obj[k])

        entries.append([filed, _round_obj(obj)])

    # Collapse entries that share a filing date (keep the last/most complete).
    dedup = {}
    for filed, obj in entries:
        dedup[filed] = obj
    return [[f, dedup[f]] for f in sorted(dedup)]


def _round_obj(obj):
    out = {}
    for k, v in obj.items():
        if v is None:
            continue
        out[k] = round(v, 4) if abs(v) < 1000 else round(v)
    return out
