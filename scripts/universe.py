"""Shared S&P 500 universe loader (pandas only, no yfinance)."""

import pandas as pd

import config


def get_universe():
    """Return a DataFrame of S&P 500 constituents from Wikipedia.

    Columns: symbol (index style, e.g. BRK.B), name, sector, yahoo (BRK-B).
    The ``yahoo`` column also matches SEC's ticker style (which uses '-').
    """
    tables = pd.read_html(config.UNIVERSE_URL)
    df = tables[0].rename(
        columns={"Symbol": "symbol", "Security": "name", "GICS Sector": "sector"}
    )[["symbol", "name", "sector"]].copy()
    df["symbol"] = df["symbol"].str.strip()
    df["yahoo"] = df["symbol"].str.replace(".", "-", regex=False)
    df = df.drop_duplicates(subset="yahoo").reset_index(drop=True)
    return df
