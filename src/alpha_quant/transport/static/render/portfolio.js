import store from "../state.js";
import { get } from "../api.js";
import { fmtCurrency, fmtPrice, fmtPct, fmtNum } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { showModal, closeModal, intro, fieldText, fieldNumber, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import { classify, ageLabel, freshnessFor } from "../freshness.js";
import { openPositionDrawer } from "./drawers.js";

const COLS = "1.7fr .7fr .9fr .9fr 1fr 1fr .7fr 1.3fr";

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

window.addEventListener("bookchange", renderPortfolio);

function symFresh(pos) {
  const f = pos.freshness || freshnessFor(pos.symbol);
  if (!f) return { severity: "live", stale: false, age_minutes: null };
  const c = classify(f.age_minutes);
  return { ...f, severity: f.severity || c.severity, stale: c.stale };
}

function buildPortfolio(p, positions) {
  const metrics = [
    metric("Equity", fmtCurrency(p.equity)),
    metric("Cash", fmtCurrency(p.cash)),
    metric("Gross exposure", fmtCurrency(p.gross_exposure)),
    metric("Drawdown", fmtPct(p.drawdown), p.drawdown > 0 ? "down" : ""),
    metric("Open positions", fmtNum(p.positions_count)),
  ].join("");

  const header = `<div class="dthead" style="grid-template-columns:${COLS}">
    <span>Symbol</span><span class="r-right">Qty</span><span class="r-right">Avg</span><span class="r-right">Price</span><span class="r-right">Mkt value</span><span class="r-right">Unreal. P&L</span><span class="r-right">Wt</span><span class="r-right">Actions</span></div>`;

  const rows = positions.map((pos) => {
    const f = symFresh(pos);
    const sevCls = f.severity === "crit" ? "fresh-badge crit" : f.severity === "warn" ? "fresh-badge warn" : "fresh-badge";
    const rowCls = f.stale ? (f.severity === "crit" ? "dtrow is-stale crit" : "dtrow is-stale") : "dtrow";
    const upl = pos.unrealized_pl;
    return `<div class="${rowCls}" style="grid-template-columns:${COLS}" data-pos="${pos.symbol}">
      <span class="symcell"><span class="sym">${pos.symbol}</span><span class="${sevCls}">${f.stale ? "STALE" : "LIVE"}</span><span class="age">${ageLabel(f.age_minutes)}</span></span>
      <span class="num">${fmtNum(pos.quantity)}</span>
      <span class="num">${fmtPrice(pos.avg_cost)}</span>
      <span class="num ink">${fmtPrice(pos.current_price)}</span>
      <span class="num ink">${fmtCurrency(pos.market_value)}</span>
      <span class="num ${upl >= 0 ? "up" : "down"}">${fmtCurrency(upl)}</span>
      <span class="num">${fmtPct(pos.portfolio_weight)}</span>
      <span class="row-acts"><button class="act-btn" data-stop="${pos.symbol}" data-stop-propagation>Stop</button><button class="act-btn danger" data-flatten="${pos.symbol}" data-stop-propagation>Flatten</button></span>
    </div>`;
  }).join("");

  return `
    <div class="metric-strip">${metrics}</div>
    <div class="sec-head"><div class="sec-title">Positions</div><span class="sec-note">Dimmed rows price off <b>stale</b> Lake data — review before trading</span></div>
    ${positions.length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No positions")}`;
}

function metric(label, value, tone = "") {
  return `<div class="metric"><span class="metric-label">${label}</span><span class="metric-value ${tone}">${value}</span></div>`;
}

function wire(positions) {
  const byId = (s) => positions.find((p) => p.symbol === s) || { symbol: s };
  document.querySelectorAll("[data-flatten]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); openFlatten(byId(b.dataset.flatten)); };
  });
  document.querySelectorAll("[data-stop]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); openStop(byId(b.dataset.stop)); };
  });
  document.querySelectorAll("[data-pos]").forEach((el) => {
    el.onclick = () => openPositionDrawer(el.dataset.pos);
  });
}

function openFlatten(pos) {
  showModal("Flatten " + pos.symbol,
    intro(`Submits a closing order for the full ${fmtNum(pos.quantity)}-share ${pos.symbol} position. Rejected on stale data unless forced.`)
      + fieldText("fl_reason", "Reason (required)", "Why flatten?"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Flatten position", class: "btn btn-danger", onclick: () => {
          const reason = val("fl_reason"); if (!reason) return;
          closeModal(); runWithToast(() => cmd.flatten(store.bookId, pos.position_id || pos.symbol, reason), "Flatten " + pos.symbol, renderPortfolio);
        } },
    ]);
}

function openStop(pos) {
  showModal("Edit stop — " + pos.symbol,
    fieldNumber("st_price", "Stop price", pos.stop_price ?? ""),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Update stop", class: "btn btn-primary", onclick: () => {
          const px = parseFloat(val("st_price")); if (!px) return;
          closeModal(); runWithToast(() => cmd.setStop(store.bookId, pos.position_id || pos.symbol, px, "Stop update from Desk"), pos.symbol + " stop " + px, renderPortfolio);
        } },
    ]);
}
