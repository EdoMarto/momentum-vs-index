# S&P 500 Momentum, paper trading vs the index

A virtual portfolio that holds the strongest S&P 500 stocks and rebalances every month, tracked live against
the S&P 500 itself. A small Python job updates it every day and a static TypeScript page shows the result.

**Live site:** https://edomarto.github.io/momentum-vs-index/

## The point
Beating the market is hard, and this project is built to show it. According to S&P's
[SPIVA](https://www.spglobal.com/spdji/en/research-insights/spiva/) scorecards, over 10 to 20 years around
85 to 95% of actively managed US large-cap funds have returned less than the S&P 500. So the honest expectation
is that a simple active strategy like this one loses to the index over time. Running it live, side by side with
the benchmark, is a concrete way to see why a cheap passive index fund is usually the smarter default.

Note that this simulation is generous to the active side: it charges no fees, trading costs, or taxes, so what
you see is a best case for the strategy. Those costs are a big part of why active investing loses in real life,
so once you add them the gap only widens. In other words, if the strategy struggles even here, that is the point.

## The strategy
Cross-sectional momentum, about as simple as it gets:
- Every month, rank all S&P 500 stocks by their last 6 months of return.
- Hold the top 20, equally weighted.
- Rebalance at the start of the next month.

The benchmark is the S&P 500 (SPY), bought once at the start with the same virtual capital and held.

Honest note: simple momentum like this does not reliably beat buy-and-hold. The point of the project is the
engine and the live, side-by-side comparison, not a promise of market-beating returns.

## How it works
- `paper_trader/` (Python): reads the ticker list, pulls daily closes from Yahoo Finance (`yfinance`), marks
  the portfolio to market, rebalances on the first trading day of each month, and writes `docs/data.json`.
- `state/`: the portfolio (holdings, cash) and the daily history, committed so they persist between runs.
- `web/` (TypeScript): the front-end source. It is bundled with esbuild into `docs/app.js` (Chart.js included).
- `docs/`: the static site served by GitHub Pages.
- `.github/workflows/update.yml`: a daily GitHub Action that runs the Python job and commits the new data, so
  the site updates on its own.

On a rebalance day the member list is refreshed from the official constituents first, so the strategy always
ranks the current S&P 500 (if that download fails, the previous list is kept). On the other days the job just
reprices what the portfolio already holds, so the list is left alone.

There is no server and no secret anywhere. Everything runs on free data and GitHub's own hosting.

It is a paper portfolio that starts from the day it went live, so there is no survivorship bias, but the track
record is only as long as the time it has been running.

## Run it yourself
```bash
pip install -r requirements.txt
python -m paper_trader.run        # updates state/ and docs/data.json

cd web
npm install
npm run build                     # rebuilds docs/app.js from the TypeScript
```
Then open `docs/index.html` (through a local server, so `fetch` can read `data.json`).

## Settings
All in `paper_trader/config.py`: starting capital, how many stocks to hold (`TOP_N`), the momentum window,
an optional trading fee, and the benchmark.

## Caveats
- Prices are free daily closes and can have gaps or the odd bad value.
- No trading costs or slippage are modelled by default (set `FEE_BPS` to add a simple fee).
- This is not investment advice.
