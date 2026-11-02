"""Tunable settings for the paper trader. Everything the strategy needs in one place."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UNIVERSE_FILE = ROOT / "universe.txt"
STATE_FILE = ROOT / "state" / "portfolio.json"
HISTORY_FILE = ROOT / "state" / "history.csv"
TRADES_FILE = ROOT / "state" / "trades.csv"
SITE_DATA_FILE = ROOT / "docs" / "data.json"

# Strategy
START_CAPITAL = 10_000.0       # virtual euros/dollars both the strategy and the benchmark start with
TOP_N = 20                     # how many stocks to hold at once, equally weighted
LOOKBACK_TRADING_DAYS = 126    # momentum window, about six months of trading days
SKIP_RECENT_DAYS = 0           # set to e.g. 21 to skip the most recent month (classic 12-1 momentum)
FEE_BPS = 0.0                  # round-trip trading fee in basis points, 0 keeps it simple (see README)

# Benchmark
BENCHMARK = "SPY"              # S&P 500 ETF

# Data
PRICE_LOOKBACK_DAYS = 400      # calendar days of history to pull so the momentum window is always covered
