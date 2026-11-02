"""Cross-sectional momentum: rank stocks by trailing return, keep the strongest N."""

from . import config


def momentum_scores(closes):
    """Return {ticker: trailing return} over the lookback window.

    The score is the price change from (lookback + skip) days ago to (skip) days ago.
    With SKIP_RECENT_DAYS = 0 that is simply the last six months of return.
    Tickers without enough history are skipped.
    """
    lookback = config.LOOKBACK_TRADING_DAYS
    skip = config.SKIP_RECENT_DAYS
    need = lookback + skip + 1
    scores = {}
    for ticker in closes.columns:
        series = closes[ticker].dropna()
        if len(series) < need:
            continue
        end = series.iloc[-1 - skip]
        start = series.iloc[-1 - skip - lookback]
        if start > 0:
            scores[ticker] = end / start - 1.0
    return scores


def pick_top(closes, n=config.TOP_N):
    """Return the n tickers with the highest momentum, best first."""
    scores = momentum_scores(closes)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [t for t, _ in ranked[:n]]
