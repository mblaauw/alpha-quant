import store from "../state.js";
import { get } from "../api.js";
import { fmtCurrency, fmtPct, fmtNum } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { openDrawer } from "../components/drawer.js";
import { renderTable } from "../components/table.js";

export async function renderPortfolio() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/portfolio");
    const positions = await get("/v1/console/positions");
    view.innerHTML = buildPortfolio(data, positions);
    document.querySelectorAll("[data-position-id]").forEach(el => {
      el.addEventListener("click", () => showPosition(el.dataset.positionId));
    });
  } catch (e) {
    view.innerHTML = errorState("Failed to load portfolio", e.message);
  }
}

function buildPortfolio(data, positions) {
  const p = data || {};
  const rows = (positions.items || []).map(pos => [
    `<span class="symbol" data-position-id="${pos.symbol}" style="cursor:pointer">${pos.symbol}</span>`,
    fmtNum(pos.quantity),
    fmtCurrency(pos.avg_cost),
    fmtCurrency(pos.current_price),
    fmtCurrency(pos.market_value),
    `<span class="${pos.unrealized_pl >= 0 ? 'positive' : 'negative'}">${fmtCurrency(pos.unrealized_pl)}</span>`,
    fmtPct(pos.portfolio_weight),
  ]);
  return `
    <div class="metric-strip">
      <div class="metric"><span class="metric-label">Equity</span><span class="metric-value">${fmtCurrency(p.equity)}</span></div>
      <div class="metric"><span class="metric-label">Cash</span><span class="metric-value">${fmtCurrency(p.cash)}</span></div>
      <div class="metric"><span class="metric-label">Gross Exposure</span><span class="metric-value">${fmtCurrency(p.gross_exposure)}</span></div>
      <div class="metric"><span class="metric-label">Drawdown</span><span class="metric-value ${p.drawdown > 0 ? 'negative' : ''}">${fmtPct(p.drawdown)}</span></div>
      <div class="metric"><span class="metric-label">Open Positions</span><span class="metric-value">${fmtNum(p.positions_count)}</span></div>
    </div>
    <div class="section-header">Positions</div>
    ${rows.length ? renderTable(["Symbol", "Qty", "Avg Cost", "Price", "Market Val", "UPL", "Weight"], rows) : emptyState("No positions")}
  `;
}

async function showPosition(symbol) {
  try {
    const pos = await get(`/v1/console/positions/${symbol}`);
    openDrawer(`Position: ${symbol}`, `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
        <div><span class="metric-label">Quantity</span><div class="metric-value">${fmtNum(pos.quantity)}</div></div>
        <div><span class="metric-label">Avg Cost</span><div class="metric-value">${fmtCurrency(pos.avg_cost)}</div></div>
        <div><span class="metric-label">Market Value</span><div class="metric-value">${fmtCurrency(pos.market_value)}</div></div>
        <div><span class="metric-label">Unreal. P&L</span><div class="metric-value ${pos.unrealized_pl >= 0 ? 'positive' : 'negative'}">${fmtCurrency(pos.unrealized_pl)}</div></div>
        <div><span class="metric-label">Stop Price</span><div class="metric-value">${fmtCurrency(pos.stop_price)}</div></div>
        <div><span class="metric-label">Weight</span><div class="metric-value">${fmtPct(pos.portfolio_weight)}</div></div>
      </div>
    `);
  } catch (e) {
    openDrawer("Error", e.message);
  }
}
