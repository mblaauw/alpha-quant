import { apiGet } from "../api.js";
import { openDrawer } from "../components/drawer.js";
import { loading, empty } from "../components/empty_state.js";

export async function renderPortfolio(container) {
  container.innerHTML = loading("Loading portfolio...");
  try {
    const summary = await apiGet("/v1/dashboard/portfolio");
    const positions = await apiGet("/v1/dashboard/positions");

    const equity = summary.equity || 0;
    const cash = summary.cash || 0;
    const mv = summary.market_value || 0;
    const exposure = mv > 0 && equity > 0 ? ((mv / equity) * 100).toFixed(1) : "0.0";

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Portfolio</h2>
      <div class="metric-grid">
        <div class="card metric-card">
          <div class="metric-label">Equity</div>
          <div class="metric-value ${equity >= 0 ? "positive" : "negative"}">$${equity.toLocaleString()}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Cash</div>
          <div class="metric-value">$${cash.toLocaleString()}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Market Value</div>
          <div class="metric-value">$${mv.toLocaleString()}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Exposure</div>
          <div class="metric-value ${exposure > 80 ? "warning" : ""}">${exposure}%</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Positions (${(positions || []).length})</div>
        <div class="card-body">
          ${(positions && positions.length > 0) ? `
            <table class="data-table">
              <thead><tr>
                <th>Symbol</th><th>Qty</th><th>Avg Cost</th><th>Price</th><th>Market Value</th><th>Unrealized P&L</th><th>Stop</th>
              </tr></thead>
              <tbody>
                ${positions.map(p => `
                  <tr class="clickable" onclick="window.__openPosition('${p.position_id || p.symbol}')">
                    <td>${p.symbol || "-"}</td>
                    <td>${p.quantity || 0}</td>
                    <td>$${(p.avg_cost || 0).toFixed(2)}</td>
                    <td>$${(p.current_price || 0).toFixed(2)}</td>
                    <td>$${(p.market_value || 0).toLocaleString()}</td>
                    <td class="${(p.unrealized_pl || 0) >= 0 ? "positive" : "negative"}">$${(p.unrealized_pl || 0).toFixed(2)}</td>
                    <td>$${(p.stop_price || 0).toFixed(2)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          ` : `<div class="empty-state"><p>No open positions</p></div>`}
        </div>
      </div>
    `;

    window.__openPosition = async (id) => {
      try {
        const detail = await apiGet(`/v1/dashboard/positions/${encodeURIComponent(id)}`);
        const pos = detail.position || {};
        const fills = detail.fills || [];
        const orders = detail.orders || [];
        openDrawer(`Position: ${pos.symbol}`, `
          <div class="kv-list" style="margin-bottom:16px">
            ${Object.entries(pos).map(([k, v]) =>
              `<div class="kv-item"><span class="kv-key">${k}</span><span class="kv-value">${typeof v === "object" ? JSON.stringify(v) : v}</span></div>`
            ).join("")}
          </div>
          <h4 style="margin-bottom:8px">Orders (${orders.length})</h4>
          ${orders.length ? `<table class="data-table">${orders.map(o => `<tr><td>${o.order_id}</td><td>${o.side}</td><td>${o.quantity}</td><td>${o.status}</td></tr>`).join("")}</table>` : "<p>No orders</p>"}
          <h4 style="margin:12px 0 8px">Fills (${fills.length})</h4>
          ${fills.length ? `<table class="data-table">${fills.map(f => `<tr><td>${f.fill_id}</td><td>${f.quantity}</td><td>$${(f.price || 0).toFixed(2)}</td></tr>`).join("")}</table>` : "<p>No fills</p>"}
        `);
      } catch (err) {
        alert("Failed: " + err.message);
      }
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load portfolio</h3><p>${err.message}</p></div>`;
  }
}
