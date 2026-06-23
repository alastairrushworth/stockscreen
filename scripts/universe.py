"""Shared S&P 500 universe loader (pandas only, no yfinance)."""

import io

import pandas as pd
import requests

import config

# Wikipedia rejects requests without a descriptive browser-style User-Agent
# (HTTP 403). Fetching via requests also uses its bundled CA certs, sidestepping
# the missing-local-issuer SSL error on some Python installs.
_USER_AGENT = (
    "Mozilla/5.0 (compatible; stockscreen-backtest/1.0; "
    "+https://github.com/alastairrushworth/stockscreen)"
)


def get_universe():
    """Return a DataFrame of S&P 500 constituents from Wikipedia.

    Columns: symbol (index style, e.g. BRK.B), name, sector, yahoo (BRK-B).
    The ``yahoo`` column also matches SEC's ticker style (which uses '-').
    """
    resp = requests.get(
        config.UNIVERSE_URL, headers={"User-Agent": _USER_AGENT}, timeout=30
    )
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0].rename(
        columns={"Symbol": "symbol", "Security": "name", "GICS Sector": "sector"}
    )[["symbol", "name", "sector"]].copy()
    df["symbol"] = df["symbol"].str.strip()
    df["yahoo"] = df["symbol"].str.replace(".", "-", regex=False)
    df = df.drop_duplicates(subset="yahoo").reset_index(drop=True)
    return df
