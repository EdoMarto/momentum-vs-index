"""Daily update: refresh prices, rebalance monthly, append to history, write the site data.

Run with:  python -m paper_trader.run
It is safe to run more than once a day; the latest trading day's point is overwritten.
"""

import csv
import json
import sys

from . import config, data, portfolio, strategy

# Windows consoles choke on some characters; keep prints safe.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def latest_trading_date(closes):
    return str(closes.index[-1].date())


def read_history():
    rows = []
    if config.HISTORY_FILE.exists():
        with open(config.HISTORY_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def write_history(rows):
    config.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "strategy", "benchmark"])
        w.writeheader()
        w.writerows(rows)


def upsert(rows, date, strat, bench):
    """Replace today's row if present, else append. Keeps one point per date."""
    for r in rows:
        if r["date"] == date:
            r["strategy"] = f"{strat:.2f}"
            r["benchmark"] = "" if bench is None else f"{bench:.2f}"
            return
    rows.append({"date": date, "strategy": f"{strat:.2f}",
                 "benchmark": "" if bench is None else f"{bench:.2f}"})


def max_drawdown(values):
    peak = None
    worst = 0.0
    for v in values:
        if peak is None or v > peak:
            peak = v
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def metrics(values, dates):
    if not values:
        return {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0}
    total = values[-1] / values[0] - 1.0
    # Days elapsed from the first to the last point.
    from datetime import date as _d
    d0 = _d.fromisoformat(dates[0])
    d1 = _d.fromisoformat(dates[-1])
    years = max((d1 - d0).days, 1) / 365.25
    cagr = (values[-1] / values[0]) ** (1 / years) - 1.0 if values[0] > 0 else 0.0
    return {"total_return": total, "cagr": cagr, "max_drawdown": max_drawdown(values)}


def need_rebalance(state, today):
    month = today[:7]  # YYYY-MM
    return state.get("last_rebalance") != month


def main():
    state = portfolio.load_state()
    universe = data.load_universe()
    first_run = state.get("started_on") is None
    today_is_rebalance = True  # decided properly once we know today's date

    # On a rebalance we need the whole universe for ranking; otherwise just what we hold.
    # We do not know today's date until we fetch, so fetch holdings+benchmark first, then
    # decide, then fetch the universe only if needed.
    held = list(state["holdings"].keys())
    base_tickers = sorted(set(held + [config.BENCHMARK]))
    base_closes = data.fetch_closes(base_tickers if not first_run else [config.BENCHMARK])
    if base_closes is None or len(base_closes) == 0:
        print("No price data returned; aborting without changes.")
        return
    today = latest_trading_date(base_closes)
    today_is_rebalance = first_run or need_rebalance(state, today)

    universe_closes = None
    if today_is_rebalance:
        universe_closes = data.fetch_closes(universe)
        if universe_closes is None:
            print("Could not fetch the universe for rebalancing; aborting.")
            return

    # Build the price map used for marking to market (latest close per ticker).
    prices = {}
    if universe_closes is not None:
        prices.update(data.latest_prices(universe_closes))
    prices.update(data.latest_prices(base_closes))

    # First run: set the start date and buy the benchmark once with the full capital.
    if first_run:
        state["started_on"] = today
        spy = prices.get(config.BENCHMARK)
        if spy:
            state["benchmark_shares"] = config.START_CAPITAL / spy

    # Rebalance into the top momentum names.
    if today_is_rebalance:
        targets = strategy.pick_top(universe_closes)
        portfolio.rebalance(state, targets, prices)
        state["last_rebalance"] = today[:7]
        print(f"Rebalanced on {today}: holding {len(state['holdings'])} names.")

    # Guard against a partial data fetch: if Yahoo dropped some of the tickers we hold,
    # the mark-to-market would be wrong. Bail out without changes; the next run fixes it.
    missing = [t for t in state["holdings"] if prices.get(t) is None]
    if missing:
        print(f"Missing prices for {len(missing)} held tickers ({', '.join(missing[:5])}"
              f"{'...' if len(missing) > 5 else ''}); aborting without changes.")
        return

    strat_val = portfolio.strategy_value(state, prices)
    bench_val = portfolio.benchmark_value(state, prices)

    rows = read_history()
    upsert(rows, today, strat_val, bench_val)
    rows.sort(key=lambda r: r["date"])
    write_history(rows)
    portfolio.save_state(state)

    write_site_data(state, rows, prices, today)
    print(f"{today}: strategy {strat_val:,.2f}  benchmark "
          f"{'n/a' if bench_val is None else f'{bench_val:,.2f}'}")


def write_site_data(state, rows, prices, today):
    dates = [r["date"] for r in rows]
    strat = [float(r["strategy"]) for r in rows]
    bench = [float(r["benchmark"]) if r["benchmark"] else None for r in rows]

    bench_clean = [(d, b) for d, b in zip(dates, bench) if b is not None]
    bench_dates = [d for d, _ in bench_clean]
    bench_vals = [b for _, b in bench_clean]

    # Current holdings with their weight in the portfolio.
    names = data.load_names()
    total = portfolio.strategy_value(state, prices)
    holdings = []
    for ticker, shares in state["holdings"].items():
        price = prices.get(ticker)
        if price:
            val = shares * price
            holdings.append({
                "ticker": ticker,
                "name": names.get(ticker, ticker),
                "weight": val / total if total else 0.0,
            })
    holdings.sort(key=lambda h: h["weight"], reverse=True)

    payload = {
        "updated": today,
        "started_on": state.get("started_on"),
        "start_capital": config.START_CAPITAL,
        "benchmark": config.BENCHMARK,
        "params": {
            "top_n": config.TOP_N,
            "lookback_trading_days": config.LOOKBACK_TRADING_DAYS,
            "rebalance": "monthly",
        },
        "series": {"dates": dates, "strategy": strat},
        "benchmark_series": {"dates": bench_dates, "values": bench_vals},
        "holdings": holdings,
        "metrics": {
            "strategy": metrics(strat, dates),
            "benchmark": metrics(bench_vals, bench_dates),
        },
    }
    config.SITE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SITE_DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
