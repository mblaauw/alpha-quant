import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { renderTable } from "../components/table.js";

export async function renderRuns() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/runs");
    view.innerHTML = buildRuns(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load runs", e.message);
  }
}

function buildRuns(data) {
  const rows = (data.items || []).map(r => [
    `<span class="mono">${r.run_id?.slice(0, 8)}</span>`,
    statusChip(r.run_type, r.run_type === "decision" ? "ready" : "neutral"),
    statusChip(r.status, r.status),
    fmtDateTime(r.started_at),
    fmtDateTime(r.completed_at),
  ]);
  return `
    <div class="section-header">Runs</div>
    ${rows.length ? renderTable(["Run ID", "Type", "Status", "Started", "Completed"], rows) : emptyState("No runs yet")}
  `;
}
