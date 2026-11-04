"""Portfolio state: what the strategy holds, plus the buy-and-hold benchmark.

State is a small JSON file so it survives between daily runs (committed by the Action).
Shares are fractional, which is fine for a paper portfolio and keeps the cash near zero.
"""

import json

from . import config


def empty_state():
    return {
        "cash": config.START_CAPITAL,
        "holdings": {},            # ticker -> shares
        "last_rebalance": None,    # YYYY-MM date of the last rebalance
        "benchmark_shares": None,  # shares of the benchmark bought once at the start
        "started_on": None,        # first date the portfolio was active
        "last_prices": {},         # last seen close per ticker, a fallback when a fetch drops one
    }


def load_state():
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return empty_state()


def save_state(state):
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def strategy_value(state, prices):
    """Mark the strategy portfolio to market with the given {ticker: price} dict."""
    value = state["cash"]
    for ticker, shares in state["holdings"].items():
        price = prices.get(ticker)
        if price is not None:
            value += shares * price
    return value


def benchmark_value(state, prices):
    shares = state.get("benchmark_shares")
    price = prices.get(config.BENCHMARK)
    if shares is None or price is None:
        return None
    return shares * price


def rebalance(state, targets, prices):
    """Move the whole portfolio into an equal-weight basket of `targets`.

    Sells everything first (back to cash), then buys each target with an equal slice.
    A simple percentage fee is charged on the traded notional if FEE_BPS is set.
    """
    fee_rate = config.FEE_BPS / 10_000.0

    # Sell current holdings.
    for ticker, shares in state["holdings"].items():
        price = prices.get(ticker)
        if price is not None:
            proceeds = shares * price
            state["cash"] += proceeds - proceeds * fee_rate
    state["holdings"] = {}

    buyable = [t for t in targets if prices.get(t)]
    if not buyable:
        return  # nothing to buy (no prices); stay in cash this cycle

    slice_value = state["cash"] / len(buyable)
    for ticker in buyable:
        price = prices[ticker]
        spend = slice_value
        fee = spend * fee_rate
        shares = (spend - fee) / price
        state["holdings"][ticker] = shares
        state["cash"] -= spend
