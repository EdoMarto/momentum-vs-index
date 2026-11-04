"""Daily update: refresh prices, rebalance monthly, append to history, write the site data.

Run with:  python -m paper_trader.run
It is safe to run more than once a day; the latest trading day's point is overwritten.
"""

import csv
import json
import sys

from . import config, data, portfolio, refresh_universe, strategy

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


def read_trades():
    rows = []
    if config.TRADES_FILE.exists():
        with open(config.TRADES_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def append_trades(new_rows):
    rows = read_trades() + new_rows
    config.TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "action", "ticker", "name"])
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


def is_month_end_trading_day(today):
    """True when `today` is the last weekday of its month (the next weekday is a new month)."""
    from datetime import date as _date, timedelta
    d = _date.fromisoformat(today)
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:  # skip Saturday and Sunday
        nxt += timedelta(days=1)
    return nxt.month != d.month


def need_rebalance(state, today):
    # Rebalance once a month, on the last trading day of the month.
    return is_month_end_trading_day(today) and state.get("last_rebalance") != today[:7]


def main():
    state = portfolio.load_state()
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

    # The S&P 500 member list is only needed to rank on a rebalance day, so refresh and load
    # it only then. On the other days we just reprice what we already hold.
    universe_closes = None
    if today_is_rebalance:
        refresh_universe.main()
        universe = data.load_universe()
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

    # Rebalance into the top momentum names, recording what entered and left the portfolio.
    if today_is_rebalance:
        names = data.load_names()
        before = set(state["holdings"])
        targets = strategy.pick_top(universe_closes)
        portfolio.rebalance(state, targets, prices)
        after = set(state["holdings"])
        trades = (
            [{"date": today, "action": "BUY", "ticker": t, "name": names.get(t, t)}
             for t in sorted(after - before)]
            + [{"date": today, "action": "SELL", "ticker": t, "name": names.get(t, t)}
               for t in sorted(before - after)]
        )
        if trades:
            append_trades(trades)
        state["last_rebalance"] = today[:7]
        print(f"Rebalanced on {today}: holding {len(state['holdings'])} names, "
              f"{len(after - before)} bought, {len(before - after)} sold.")

    # Recover any tickers the batch download dropped, so one flaky symbol does not skip the day:
    # first retry it on its own, then fall back to the last price we saw on an earlier run.
    last_prices = state.get("last_prices", {}) or {}
    needed = list(state["holdings"]) + [config.BENCHMARK]
    for t in [t for t in needed if prices.get(t) is None]:
        p = data.latest_price_single(t)
        if p is not None:
            prices[t] = p
    for t in [t for t in needed if prices.get(t) is None]:
        if last_prices.get(t) is not None:
            prices[t] = last_prices[t]
            print(f"Using last known price for {t} (Yahoo had no data today).")

    # Only a truly unknown holding (never priced before) blocks the update.
    unknown = [t for t in state["holdings"] if prices.get(t) is None]
    if unknown:
        print(f"No price for {len(unknown)} held tickers ({', '.join(unknown[:5])}); aborting.")
        return

    # Remember today's prices as tomorrow's fallback.
    state["last_prices"] = {**last_prices, **{t: v for t, v in prices.items() if v is not None}}

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
        "trades": list(reversed(read_trades())),  # full log, most recent first
        "metrics": {
            "strategy": metrics(strat, dates),
            "benchmark": metrics(bench_vals, bench_dates),
        },
    }
    config.SITE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SITE_DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
