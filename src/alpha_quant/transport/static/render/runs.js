import { apiGet } from "../api.js";
import { openDrawer } from "../components/drawer.js";
import { loading } from "../components/empty_state.js";

export async function renderRuns(container) {
  container.innerHTML = loading("Loading runs...");
  try {
    const data = await apiGet("/v1/dashboard/runs");
    const items = data.items || [];

    if (items.length === 0) {
      container.innerHTML = `<div class="empty-state"><h3>No runs yet</h3><p>Run history will appear after the first pipeline execution.</p></div>`;
      return;
    }

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Runs</h2>
      <div class="card">
        <table class="data-table">
          <thead><tr>
            <th>Run ID</th><th>Type</th><th>Status</th><th>Started</th><th>Completed</th>
          </tr></thead>
          <tbody>
            ${items.map(r => `
              <tr class="clickable" onclick="window.__openRun('${r.run_id}')">
                <td>${(r.run_id || "").slice(0, 12)}</td>
                <td>${r.run_type || "-"}</td>
                <td><span class="status-dot ${r.status === "completed" ? "healthy" : r.status === "failed" ? "critical" : "warning"}"></span>${r.status || "-"}</td>
                <td>${r.started_at ? new Date(r.started_at).toLocaleString() : "-"}</td>
                <td>${r.completed_at ? new Date(r.completed_at).toLocaleString() : "-"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;

    window.__openRun = async (runId) => {
      try {
        const detail = await apiGet(`/v1/dashboard/runs/${encodeURIComponent(runId)}`);
        const run = detail.run || {};
        const decisions = detail.decisions || [];
        openDrawer(`Run: ${runId.slice(0, 12)}`, `
          <div class="kv-list" style="margin-bottom:16px">
            ${Object.entries(run).map(([k, v]) =>
              `<div class="kv-item"><span class="kv-key">${k}</span><span class="kv-value">${typeof v === "object" ? JSON.stringify(v) : String(v)}</span></div>`
            ).join("")}
          </div>
          ${decisions.length ? `<h4 style="margin-bottom:8px">Decisions (${decisions.length})</h4>
            <table class="data-table">${decisions.map(d => `<tr><td>${d.symbol}</td><td>${d.action || d.decision}</td><td>${d.score?.toFixed(2) || ""}</td></tr>`).join("")}</table>`
          : ""}
        `);
      } catch (err) {
        alert("Failed: " + err.message);
      }
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load runs</h3><p>${err.message}</p></div>`;
  }
}
