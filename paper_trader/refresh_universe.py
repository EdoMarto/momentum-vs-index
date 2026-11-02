"""Refresh the ticker universe and the ticker -> name map from the official S&P 500 list.

Run with:  python -m paper_trader.refresh_universe

Downloads the public constituents CSV and rewrites universe.txt and names.json so the
strategy always ranks the current members of the index. If the download fails or looks
wrong, the existing files are left untouched (a bad fetch must never wipe the universe).
"""

import csv
import io
import json
import urllib.request

from . import config

SOURCE_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)
NAMES_FILE = config.ROOT / "paper_trader" / "names.json"
MIN_EXPECTED = 400  # the index has ~500 names; far fewer means a broken download


def fetch_constituents():
    raw = urllib.request.urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
    names = {}
    for row in csv.DictReader(io.StringIO(raw)):
        symbol = row["Symbol"].strip().replace(".", "-")  # Yahoo uses dashes (BRK-B)
        name = row["Security"].strip()
        if symbol:
            names[symbol] = name or symbol
    return names


def main():
    try:
        names = fetch_constituents()
    except Exception as e:  # network or parse error: keep what we have
        print(f"Could not refresh the universe ({e}); keeping the existing list.")
        return

    if len(names) < MIN_EXPECTED:
        print(f"Only {len(names)} names fetched (< {MIN_EXPECTED}); keeping the existing list.")
        return

    tickers = sorted(names)
    header = "# S&P 500 members, refreshed automatically from the official constituents list.\n"
    config.UNIVERSE_FILE.write_text(header + "\n".join(tickers) + "\n", encoding="utf-8")
    NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Universe refreshed: {len(tickers)} tickers.")


if __name__ == "__main__":
    main()
