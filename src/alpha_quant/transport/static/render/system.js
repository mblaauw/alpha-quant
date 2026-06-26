import { apiGet } from "../api.js";
import { loading } from "../components/empty_state.js";

export async function renderSystem(container) {
  container.innerHTML = loading("Loading system info...");
  try {
    const sys = await apiGet("/v1/dashboard/system");
    const ctx = await apiGet("/v1/dashboard/context");

    container.innerHTML = `
      <h2 style="margin-bottom:20px">System</h2>

      <div class="card" style="margin-bottom:16px">
        <div class="card-header">Service Health</div>
        <div class="card-body">
          ${sys.components ? Object.entries(sys.components).map(([name, info]) => `
            <div class="status-row">
              <span class="status-label">${name}</span>
              <span class="status-value"><span class="status-dot ${info.healthy ? "healthy" : "critical"}"></span>${info.healthy ? "Healthy" : "Unhealthy"}</span>
            </div>
          `).join("") : `<div class="empty-state"><p>No component data available</p></div>`}
        </div>
      </div>

      <div class="card">
        <div class="card-header">Operational Context</div>
        <div class="card-body">
          <div class="kv-list">
            <div class="kv-item"><span class="kv-key">Halted</span><span class="kv-value">${ctx.halted ? "Yes" : "No"}</span></div>
            <div class="kv-item"><span class="kv-key">Last Run</span><span class="kv-value">${ctx.last_run_id || "-"}</span></div>
            <div class="kv-item"><span class="kv-key">Last Run Status</span><span class="kv-value">${ctx.last_run_status || "-"}</span></div>
            <div class="kv-item"><span class="kv-key">Last Run As Of</span><span class="kv-value">${ctx.last_run_as_of || "-"}</span></div>
          </div>
        </div>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load system info</h3><p>${err.message}</p></div>`;
  }
}
