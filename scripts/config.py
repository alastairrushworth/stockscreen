"""Configuration for the data-fetch jobs."""

import os

# Where the S&P 500 constituent list comes from (free, no key).
UNIVERSE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# How much daily price history to download. Monthly-resampled prices from this
# window power the backtest; the daily tail powers current momentum/vol metrics.
# 15y pairs with the depth of free SEC fundamentals (~2010+).
PRICE_PERIOD = "15y"

# Pandas resample rule for the monthly backtest matrix ("ME" = month-end).
MONTHLY_RULE = "ME"

# Throttle / retry for the per-ticker fundamentals fetch (Yahoo rate-limits).
REQUEST_SLEEP = 0.3      # seconds between fundamental requests
MAX_RETRIES = 3

# Output location (served as-is by GitHub Pages).
DATA_DIR = "data"

# Round prices in the monthly matrix to keep the browser payload small.
PRICE_DECIMALS = 3

# --- SEC EDGAR (historical point-in-time fundamentals) ---------------------- #
# SEC requires a descriptive User-Agent with contact info. Override via env var.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "stockscreen-backtest (set SEC_USER_AGENT env var with contact)"
)
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SLEEP = 0.12          # seconds between requests (~8/s, under SEC's 10/s cap)
SEC_MAX_RETRIES = 4
SEC_CACHE_DIR = os.environ.get("SEC_CACHE_DIR", ".cache/sec")  # gitignored
# Drop fundamental entries filed before this (keeps the JSON bounded). Set to
# None to keep everything SEC has.
HISTORY_START = "2009-06-01"
