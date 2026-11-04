"""Price data access via Yahoo Finance (yfinance). Free daily close prices."""

import json

import yfinance as yf

from . import config

_NAMES_FILE = config.ROOT / "paper_trader" / "names.json"


def load_names():
    """Map of ticker -> company name, for showing friendly names on the site."""
    if _NAMES_FILE.exists():
        return json.loads(_NAMES_FILE.read_text(encoding="utf-8"))
    return {}


def load_universe():
    """Read the ticker list, one symbol per line, skipping blanks and comments."""
    out = []
    for line in config.UNIVERSE_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def fetch_closes(tickers, days=config.PRICE_LOOKBACK_DAYS):
    """Return a DataFrame of daily adjusted closes (columns = tickers, index = dates).

    Tickers that Yahoo has no data for are simply absent from the result.
    """
    if not tickers:
        return None
    period = f"{max(days, 5)}d"
    data = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data is None or len(data) == 0:
        return None
    # With several tickers yfinance returns a column MultiIndex; "Close" holds the adjusted closes.
    if hasattr(data.columns, "levels"):
        closes = data["Close"]
    else:
        # Single ticker: flat columns. Wrap the Close series under the ticker name.
        closes = data[["Close"]].rename(columns={"Close": tickers[0]})
    return closes.dropna(how="all")


def latest_prices(closes):
    """Last available close for each ticker as a plain dict, dropping missing values."""
    last = closes.ffill().iloc[-1]
    return {t: float(p) for t, p in last.items() if p == p}  # p == p drops NaN


def latest_price_single(ticker, days=config.PRICE_LOOKBACK_DAYS):
    """Latest close for one ticker, fetched on its own. Used to recover a name the batch
    download dropped (Yahoo often returns a single-ticker request fine). None if unavailable."""
    df = fetch_closes([ticker], days)
    if df is None or ticker not in getattr(df, "columns", []):
        return None
    series = df[ticker].ffill()
    if len(series) == 0:
        return None
    v = float(series.iloc[-1])
    return v if v == v else None
