import store from "../state.js";
import { get } from "../api.js";
import { fmtCurrency, fmtPct, fmtDateTime, fmtNum } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";

export async function renderDesk() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;

  try {
    const data = await get("/v1/console/desk");
    view.innerHTML = buildDesk(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load desk", e.message);
  }
}

function buildDesk(data) {
  const p = data.portfolio || {};
  return `
    <div class="metric-strip">
      <div class="metric"><span class="metric-label">Equity</span><span class="metric-value">${fmtCurrency(p.equity)}</span></div>
      <div class="metric"><span class="metric-label">Cash</span><span class="metric-value">${fmtCurrency(p.cash)}</span></div>
      <div class="metric"><span class="metric-label">Gross Exposure</span><span class="metric-value">${fmtCurrency(p.gross_exposure)}</span></div>
      <div class="metric"><span class="metric-label">Positions</span><span class="metric-value">${fmtNum(p.positions_count)}</span></div>
      <div class="metric"><span class="metric-label">Pending Commands</span><span class="metric-value">${fmtNum(data.pending_commands)}</span></div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">Operational Readiness</div>
        ${buildReadiness(data)}
      </div>
      <div class="card">
        <div class="card-header">Latest Decision Run</div>
        ${buildLatestRun(data)}
      </div>
    </div>

    <div style="margin-top:1rem" class="grid-2">
      <div class="card">
        <div class="card-header">Attention Queue</div>
        ${data.halted ? `<div style="color:var(--aq-negative)">● System is halted — ${data.halt_reason || "No reason given"}</div>` : emptyState("No active alerts")}
      </div>
      <div class="card">
        <div class="card-header">Portfolio Change</div>
        ${data.recent_decisions && data.recent_decisions.length ? `Last decision evaluated ${data.recent_decisions.length} candidates` : emptyState("No recent activity")}
      </div>
    </div>
  `;
}

function buildReadiness(data) {
  const checks = data.health_checks || {};
  return Object.entries(checks).map(([k, v]) =>
    `<div style="display:flex;justify-content:space-between;padding:4px 0"><span>${k}</span>${statusChip(v.status, v.healthy ? "healthy" : "halted")}</div>`
  ).join("");
}

function buildLatestRun(data) {
  const r = data.last_run;
  if (!r) return emptyState("No run yet");
  return `<div style="display:grid;gap:4px"><span>${statusChip(r.status, r.status)}</span><span style="font-family:var(--aq-font-mono);font-size:0.8rem">${fmtDateTime(r.completed_at)}</span><span>${r.candidates_evaluated || 0} candidates</span></div>`;
}
