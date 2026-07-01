import store from "../state.js";
import { get } from "../api.js";
import { fmtCurrency, fmtPrice, fmtPct, fmtNum, esc } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { classify, ageLabel, freshnessFor } from "../freshness.js";
import { openPositionDrawer } from "./drawers.js";

const COLS = "1.7fr .7fr .9fr .9fr 1fr 1fr .7fr .5fr";

export async function renderPortfolio() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const bid = store.bookId ? "?book_id=" + store.bookId : "";
  try {
    const [data, positions] = await Promise.all([get("/v1/console/portfolio" + bid), get("/v1/console/positions" + bid)]);
    view.innerHTML = buildPortfolio(data, positions.items || []);
    wire(positions.items || []);
  } catch (e) {
    view.innerHTML = errorState("Failed to load portfolio", e.message);
  }
}

window.addEventListener("bookchange", () => { if (store.route === "portfolio") renderPortfolio(); });

function symFresh(pos) {
  const f = pos.freshness || freshnessFor(pos.symbol);
  if (!f) return { severity: "live", stale: false, age_minutes: null };
  const c = classify(f.age_minutes);
  return { ...f, severity: f.severity || c.severity, stale: c.stale };
}

function buildPortfolio(p, positions) {
  const totalPl = positions.reduce((s, pos) => s + (pos.unrealized_pl || 0), 0);
  const grossExposure = positions.reduce((s, pos) => s + (pos.market_value || 0), 0);
  const eq = p.equity || 1;
  const metrics = [
    `<div class="metric"><span class="metric-label">Equity</span><span class="metric-value">${fmtCurrency(p.equity)}</span></div>`,
    `<div class="metric"><span class="metric-label">Cash</span><span class="metric-value">${fmtCurrency(p.cash)}</span></div>`,
    `<div class="metric"><span class="metric-label">Gross exposure</span><span class="metric-value">${fmtCurrency(grossExposure)}</span><span class="metric-sub">${fmtPct(grossExposure / eq)} of equity</span></div>`,
    `<div class="metric"><span class="metric-label">Unrealized P&amp;L</span><span class="metric-value" data-tone="${totalPl >= 0 ? "up" : "down"}">${fmtCurrency(totalPl)}</span><span class="metric-sub">open positions</span></div>`,
    `<div class="metric"><span class="metric-label">Open positions</span><span class="metric-value">${fmtNum(p.positions_count || positions.length)}</span></div>`,
  ].join("");

  const header = `<div class="dthead" style="grid-template-columns:${COLS}">
    <span>Symbol</span><span class="r-right">Qty</span><span class="r-right">Avg</span><span class="r-right">Price</span><span class="r-right">Mkt value</span><span class="r-right">Unreal. P&amp;L</span><span class="r-right">Wt</span><span></span></div>`;

  const rows = positions.map((pos) => {
    const f = symFresh(pos);
    const sev = f.severity || "live";
    const badgeLabel = f.stale ? "STALE" : "LIVE";
    const rowStale = f.stale ? (sev === "crit" ? "crit" : "warn") : "";
    const upl = pos.unrealized_pl || 0;
    return `<div class="dtrow" data-stale="${rowStale}" style="grid-template-columns:${COLS}" data-pos="${pos.symbol}">
      <span class="symcell">
        <span class="sym">${esc(pos.symbol)}</span>
        <span class="fresh-badge" data-sev="${sev}">${badgeLabel}</span>
        <span class="age">${ageLabel(f.age_minutes)}</span>
      </span>
      <span class="num" data-ink="true">${fmtNum(pos.quantity)}</span>
      <span class="num">${fmtPrice(pos.avg_cost)}</span>
      <span class="num" data-ink="true">${fmtPrice(pos.current_price)}</span>
      <span class="num" data-ink="true">${fmtCurrency(pos.market_value)}</span>
      <span class="num" data-tone="${upl >= 0 ? "up" : "down"}">${fmtCurrency(upl)}</span>
      <span class="num">${fmtPct(pos.portfolio_weight)}</span>
      <span class="chev">›</span>
    </div>`;
  }).join("");

  return `
    <div class="metric-strip">${metrics}</div>
    <div class="sec-head"><div class="sec-title">Positions</div><span class="sec-note">Dimmed rows price off <b>stale</b> Lake data — review before trading</span></div>
    ${positions.length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No positions")}`;
}

function wire(positions) {
  document.querySelectorAll("[data-pos]").forEach((el) => {
    el.onclick = () => openPositionDrawer(el.dataset.pos);
  });
}
