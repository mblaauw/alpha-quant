import { apiGet } from "../api.js";
import { showCommandConfirm } from "../commands.js";
import { loading, empty } from "../components/empty_state.js";

export async function renderCommandCenter(container) {
  container.innerHTML = loading("Loading command center...");
  try {
    const data = await apiGet("/v1/dashboard/command-center");
    const portfolio = data.portfolio || {};
    const equity = portfolio?.equity || 0;
    const cash = portfolio?.cash || 0;
    const mv = portfolio?.market_value || 0;
    const exposure = mv > 0 && equity > 0 ? ((mv / equity) * 100).toFixed(1) : "0.0";

    container.innerHTML = `
      <h2 style="margin-bottom:20px">Command Center</h2>

      <div class="metric-grid">
        <div class="card metric-card">
          <div class="metric-label">Portfolio Equity</div>
          <div class="metric-value ${equity >= 0 ? "positive" : "negative"}">$${equity.toLocaleString()}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Available Cash</div>
          <div class="metric-value">$${cash.toLocaleString()}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Open Exposure</div>
          <div class="metric-value ${exposure > 80 ? "warning" : ""}">${exposure}%</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Open Positions</div>
          <div class="metric-value">${data.positions_count || 0}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Pending Commands</div>
          <div class="metric-value">${data.pending_commands || 0}</div>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px">
        <div class="card-header">Operational Readiness</div>
        <div class="card-body">
          <div style="display:flex;gap:24px;flex-wrap:wrap">
            <span><span class="status-dot healthy"></span>PostgreSQL</span>
            <span id="lake-readiness"><span class="status-dot healthy"></span>Alpha-Lake</span>
            <span id="halt-readiness"><span class="status-dot ${data.halted ? "critical" : "healthy"}"></span>${data.halted ? "HALTED" : "Ready"}</span>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px">
        <div class="card-header">Last Decision Run</div>
        <div class="card-body">
          ${data.last_run ? `
            <div class="kv-list">
              <div class="kv-item"><span class="kv-key">Run ID</span><span class="kv-value">${data.last_run.run_id || "-"}</span></div>
              <div class="kv-item"><span class="kv-key">Status</span><span class="kv-value">${data.last_run.status || "-"}</span></div>
              <div class="kv-item"><span class="kv-key">Decisions</span><span class="kv-value">${(data.recent_decisions || []).length}</span></div>
            </div>
          ` : `<div class="empty-state"><p>No runs yet</p></div>`}
        </div>
      </div>

      <div style="display:flex;gap:8px">
        <button class="btn btn-primary" onclick="window.__navigateRun()">▶ Run Decision Cycle</button>
        <button class="btn btn-danger" onclick="window.__navigateHalt()">⏹ Halt System</button>
      </div>
    `;

    window.__navigateRun = () => {
      showCommandConfirm({
        type: "decision_run.create",
        title: "Run Decision Cycle",
        description: "Execute a full decision pipeline using current Alpha-Lake state.",
        fields: [{ name: "reason", label: "Reason", type: "text", required: false, value: "Manual run" }],
      });
    };

    window.__navigateHalt = () => {
      showCommandConfirm({
        type: "halt.create",
        title: "Halt System",
        description: "This will prevent new decision cycles and paper executions.",
        fields: [{ name: "reason", label: "Reason", type: "text", required: true }],
        danger: true,
      });
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load command center</h3><p>${err.message}</p></div>`;
  }
}
