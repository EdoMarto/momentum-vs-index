import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

const REPO_URL = "https://github.com/EdoMarto/momentum-vs-index";

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
  trades: { date: string; action: string; ticker: string; name: string }[];
  metrics: { strategy: Metrics; benchmark: Metrics };
}

const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
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
  const lastBench = d.benchmark_series.values[d.benchmark_series.values.length - 1] ?? d.start_capital;
  const edge = s.total_return - b.total_return;
  document.getElementById("cards-strategy")!.innerHTML = [
    card("Strategy value", money(lastStrat), signed(s.total_return) + " total", cls(s.total_return)),
    card("Strategy return", signed(s.total_return), "CAGR " + signed(s.cagr), cls(s.total_return)),
    card("Strategy max drawdown", pct(s.max_drawdown), "deepest fall from a peak", cls(s.max_drawdown)),
  ].join("");
  document.getElementById("cards-benchmark")!.innerHTML = [
    card("S&P 500 value", money(lastBench), signed(b.total_return) + " total", cls(b.total_return)),
    card("S&P 500 return", signed(b.total_return), "CAGR " + signed(b.cagr), cls(b.total_return)),
    card("S&P 500 max drawdown", pct(b.max_drawdown), "deepest fall from a peak", cls(b.max_drawdown)),
  ].join("");
  document.getElementById("cards-edge")!.innerHTML = card(
    "Edge vs index",
    signed(edge),
    "strategy minus benchmark",
    cls(edge),
  );
}

interface Range {
  key: string;
  days?: number; // window length in calendar days
  ytd?: boolean; // from Jan 1 of the last point's year
  all?: boolean; // whole history
}
const RANGES: Range[] = [
  { key: "1D", days: 1 },
  { key: "1M", days: 30 },
  { key: "3M", days: 91 },
  { key: "YTD", ytd: true },
  { key: "1Y", days: 365 },
  { key: "3Y", days: 365 * 3 },
  { key: "5Y", days: 365 * 5 },
  { key: "Max", all: true },
];
const DEFAULT_RANGE = "Max";

let chart: Chart | null = null;
let chartData: Data | null = null;

function cutoffDate(dates: string[], r: Range): string | null {
  if (r.all || dates.length === 0) return null;
  const last = dates[dates.length - 1];
  if (r.ytd) return `${last.slice(0, 4)}-01-01`;
  const c = new Date(last + "T00:00:00Z");
  c.setUTCDate(c.getUTCDate() - (r.days ?? 0));
  return c.toISOString().slice(0, 10);
}

function drawChart(r: Range): void {
  const d = chartData!;
  const dates = d.series.dates;
  const cutoff = cutoffDate(dates, r);
  let idx = dates.map((_, i) => i);
  if (cutoff) idx = idx.filter((i) => dates[i] >= cutoff);
  if (idx.length < 2 && dates.length >= 2) idx = [dates.length - 2, dates.length - 1]; // keep a line visible

  const labels = idx.map((i) => dates[i]);
  const strat = idx.map((i) => d.series.strategy[i]);
  const benchByDate = new Map(d.benchmark_series.dates.map((dt, i) => [dt, d.benchmark_series.values[i]]));
  const benchAligned = labels.map((dt) => benchByDate.get(dt) ?? null);

  if (chart) chart.destroy();
  const ctx = document.getElementById("chart") as HTMLCanvasElement;
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Momentum strategy", data: strat, borderColor: "#4c8dff", fill: false, tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: `${d.benchmark} (S&P 500)`, data: benchAligned, borderColor: "#f0a020", fill: false, tension: 0.15, pointRadius: 0, borderWidth: 2, spanGaps: true },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxTicksLimit: 8, color: "#9aa4b2" }, grid: { color: "#242a32" } },
        y: { ticks: { color: "#9aa4b2", callback: (v) => money(Number(v)) }, grid: { color: "#242a32" } },
      },
      plugins: {
        legend: { labels: { color: "#e6e9ee" } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${money(Number(c.parsed.y))}` } },
      },
    },
  });
}

function renderChart(d: Data): void {
  chartData = d;
  const bar = document.getElementById("chart-ranges")!;
  bar.innerHTML = RANGES.map(
    (r) => `<button class="range-btn${r.key === DEFAULT_RANGE ? " active" : ""}" data-range="${r.key}">${r.key}</button>`,
  ).join("");
  bar.querySelectorAll<HTMLButtonElement>("button[data-range]").forEach((b) =>
    b.addEventListener("click", () => {
      bar.querySelectorAll(".range-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      drawChart(RANGES.find((r) => r.key === b.dataset.range)!);
    }),
  );
  drawChart(RANGES.find((r) => r.key === DEFAULT_RANGE)!);
}

function renderHoldings(d: Data): void {
  const body = document.querySelector("#holdings tbody")!;
  body.innerHTML = d.holdings
    .map(
      (h) =>
        `<tr><td class="tk">${esc(h.ticker)}</td><td>${esc(h.name ?? h.ticker)}</td><td>${pct(h.weight)}</td></tr>`,
    )
    .join("");
}

type Trade = Data["trades"][number];
let allTrades: Trade[] = [];

function tradeRows(rows: Trade[]): string {
  if (rows.length === 0) {
    return `<tr><td colspan="4" class="empty">No trades match this filter.</td></tr>`;
  }
  return rows
    .map((t) => {
      const buy = t.action === "BUY";
      const tag = `<span class="trade ${buy ? "buy" : "sell"}">${buy ? "Bought" : "Sold"}</span>`;
      return `<tr><td>${esc(t.date)}</td><td>${tag}</td><td class="tk">${esc(t.ticker)}</td><td>${esc(
        t.name ?? t.ticker,
      )}</td></tr>`;
    })
    .join("");
}

function applyTradeFilters(): void {
  const q = (document.getElementById("trade-search") as HTMLInputElement).value.trim().toLowerCase();
  const action = (document.getElementById("trade-action") as HTMLSelectElement).value;
  const filtered = allTrades.filter((t) => {
    if (action !== "ALL" && t.action !== action) return false;
    if (q && !`${t.ticker} ${t.name ?? ""}`.toLowerCase().includes(q)) return false;
    return true;
  });
  document.querySelector("#trades tbody")!.innerHTML = tradeRows(filtered);
  document.getElementById("trades-count")!.textContent =
    filtered.length === allTrades.length ? `(${allTrades.length})` : `(${filtered.length} of ${allTrades.length})`;
}

function renderTrades(d: Data): void {
  allTrades = d.trades ?? [];
  document.getElementById("trade-search")!.addEventListener("input", applyTradeFilters);
  document.getElementById("trade-action")!.addEventListener("change", applyTradeFilters);
  applyTradeFilters();
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
  renderTrades(d);
  renderMeta(d);
}

main().catch((e) => {
  document.getElementById("cards-strategy")!.textContent = "Could not load data: " + e;
});
