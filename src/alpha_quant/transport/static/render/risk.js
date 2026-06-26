import { apiGet } from "../api.js";
import { showCommandConfirm } from "../commands.js";
import { loading } from "../components/empty_state.js";

export async function renderRisk(container) {
  container.innerHTML = loading("Loading risk data...");
  try {
    const risk = await apiGet("/v1/dashboard/risk");
    const halts = await apiGet("/v1/dashboard/halts");

    const halted = risk.halted || halts.halted;
    const halt = risk.halt || halts.halt;
    const nearStop = risk.near_stop || [];

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Risk &amp; Halts</h2>

      <div class="metric-grid">
        <div class="card metric-card">
          <div class="metric-label">System Status</div>
          <div class="metric-value ${halted ? "negative" : "positive"}">${halted ? "HALTED" : "Ready"}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Positions</div>
          <div class="metric-value">${risk.positions_count || 0}</div>
        </div>
        <div class="card metric-card">
          <div class="metric-label">Near Stop</div>
          <div class="metric-value ${nearStop.length > 0 ? "warning" : ""}">${nearStop.length}</div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-header">Halt State</div>
        <div class="card-body">
          ${halted ? `
            <div class="kv-list">
              <div class="kv-item"><span class="kv-key">Reason</span><span class="kv-value">${halt?.reason || "Unknown"}</span></div>
              <div class="kv-item"><span class="kv-key">Started</span><span class="kv-value">${halt?.created_at || "-"}</span></div>
            </div>
            <button class="btn btn-primary" style="margin-top:12px" onclick="window.__resumeSystem()">▶ Resume System</button>
          ` : `
            <div class="empty-state"><p>System is operational. No active halt.</p></div>
            <button class="btn btn-danger" style="margin-top:12px" onclick="window.__haltSystem()">⏹ Halt System</button>
          `}
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-header">Positions Near Stop (${nearStop.length})</div>
        <div class="card-body">
          ${nearStop.length ? `
            <table class="data-table">
              <thead><tr><th>Symbol</th><th>Dist to Stop %</th></tr></thead>
              <tbody>
                ${nearStop.map(n => `<tr><td>${n.symbol}</td><td class="warning">${n.dist_to_stop_pct}%</td></tr>`).join("")}
              </tbody>
            </table>
          ` : `<p>No positions near stop.</p>`}
        </div>
      </div>

      <div class="card">
        <div class="card-header">Recent Risk Events</div>
        <div class="card-body">
          ${(risk.recent_risk_events || []).length ? `
            <table class="data-table">
              <thead><tr><th>Event</th><th>Timestamp</th></tr></thead>
              <tbody>
                ${risk.recent_risk_events.map(e => `<tr><td>${e.event_type || e.reason || "-"}</td><td>${e.created_at || e.timestamp || "-"}</td></tr>`).join("")}
              </tbody>
            </table>
          ` : `<p>No recent risk events.</p>`}
        </div>
      </div>
    `;

    window.__haltSystem = () => {
      showCommandConfirm({
        type: "halt.create",
        title: "Halt System",
        description: "Prevent new decision cycles and paper executions.",
        fields: [{ name: "reason", label: "Reason", type: "text", required: true }],
        danger: true,
      });
    };

    window.__resumeSystem = () => {
      showCommandConfirm({
        type: "halt.resume",
        title: "Resume System",
        description: "Re-enable decision cycles and paper executions.",
        fields: [{ name: "reason", label: "Reason", type: "text", required: true }],
      });
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load risk data</h3><p>${err.message}</p></div>`;
  }
}
