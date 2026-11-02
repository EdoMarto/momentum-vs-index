import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

const REPO_URL = "https://github.com/EdoMarto/sp500-momentum-paper";

interface Metrics {
  total_return: number;
  cagr: number;
  max_drawdown: number;
}

interface Data {
  updated: string;
  started_on: string;
  start_capital: number;
  benchmark: string;
  params: { top_n: number; lookback_trading_days: number; rebalance: string };
  series: { dates: string[]; strategy: number[] };
  benchmark_series: { dates: string[]; values: number[] };
  holdings: { ticker: string; name: string; weight: number }[];
  metrics: { strategy: Metrics; benchmark: Metrics };
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const signed = (x: number) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;
const money = (x: number) =>
  x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const cls = (x: number) => (x >= 0 ? "pos" : "neg");

function card(label: string, value: string, sub = "", valueClass = ""): string {
  return `<div class="card">
    <div class="label">${label}</div>
    <div class="value ${valueClass}">${value}</div>
    ${sub ? `<div class="sub2">${sub}</div>` : ""}
  </div>`;
}

function renderCards(d: Data): void {
  const s = d.metrics.strategy;
  const b = d.metrics.benchmark;
  const lastStrat = d.series.strategy[d.series.strategy.length - 1] ?? d.start_capital;
  const edge = s.total_return - b.total_return;
  const el = document.getElementById("cards")!;
  el.innerHTML = [
    card("Strategy value", money(lastStrat), signed(s.total_return) + " total", cls(s.total_return)),
    card("Strategy return", signed(s.total_return), "CAGR " + signed(s.cagr), cls(s.total_return)),
    card(`${d.benchmark} return`, signed(b.total_return), "CAGR " + signed(b.cagr), cls(b.total_return)),
    card("Edge vs index", signed(edge), "strategy minus benchmark", cls(edge)),
    card("Strategy max drawdown", pct(s.max_drawdown), "deepest fall from a peak", cls(s.max_drawdown)),
  ].join("");
}

function renderChart(d: Data): void {
  const benchByDate = new Map(d.benchmark_series.dates.map((dt, i) => [dt, d.benchmark_series.values[i]]));
  const labels = d.series.dates;
  const benchAligned = labels.map((dt) => benchByDate.get(dt) ?? null);

  const ctx = document.getElementById("chart") as HTMLCanvasElement;
  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Momentum strategy",
          data: d.series.strategy,
          borderColor: "#4c8dff",
          backgroundColor: "rgba(76,141,255,0.12)",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: `${d.benchmark} (S&P 500)`,
          data: benchAligned,
          borderColor: "#f0a020",
          fill: false,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
          spanGaps: true,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 8, color: "#9aa4b2" }, grid: { color: "#242a32" } },
        y: {
          ticks: {
            color: "#9aa4b2",
            callback: (v) => money(Number(v)),
          },
          grid: { color: "#242a32" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e6e9ee" } },
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label}: ${money(Number(c.parsed.y))}`,
          },
        },
      },
    },
  });
}

function renderHoldings(d: Data): void {
  const body = document.querySelector("#holdings tbody")!;
  const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
  body.innerHTML = d.holdings
    .map(
      (h) =>
        `<tr><td class="tk">${esc(h.ticker)}</td><td>${esc(h.name ?? h.ticker)}</td><td>${pct(h.weight)}</td></tr>`,
    )
    .join("");
}

function renderMeta(d: Data): void {
  const meta = document.getElementById("meta")!;
  meta.textContent =
    `Live since ${d.started_on}, last updated ${d.updated}. ` +
    `Holds the top ${d.params.top_n} S&P 500 stocks by ${Math.round(d.params.lookback_trading_days / 21)}-month ` +
    `return, rebalanced ${d.params.rebalance}. Both start at ${money(d.start_capital)}.`;
  const link = document.getElementById("repo-link") as HTMLAnchorElement;
  link.href = REPO_URL;
}

async function main(): Promise<void> {
  const res = await fetch("data.json?t=" + Date.now());
  const d: Data = await res.json();
  renderCards(d);
  renderChart(d);
  renderHoldings(d);
  renderMeta(d);
}

main().catch((e) => {
  document.getElementById("cards")!.textContent = "Could not load data: " + e;
});
