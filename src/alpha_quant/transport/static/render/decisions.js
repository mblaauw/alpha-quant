import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime, fmtPct } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { renderTable } from "../components/table.js";

export async function renderDecisions() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/decisions?" + new URLSearchParams(store.filters).toString());
    view.innerHTML = buildDecisions(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load decisions", e.message);
  }
}

function buildDecisions(data) {
  const rows = (data.items || []).map(d => [
    d.symbol,
    statusChip(d.decision, d.decision === "enter" ? "healthy" : d.decision === "blocked" ? "halted" : "neutral"),
    d.eligibility || "—",
    `<span class="mono">${d.rank ?? "—"}</span>`,
    `<span class="mono">${d.composite_score != null ? fmtPct(d.composite_score) : "—"}</span>`,
    d.reason || "—",
    fmtDateTime(d.decision_date),
  ]);
  return `
    <div class="section-header">Decisions</div>
    ${rows.length ? renderTable(["Symbol", "Decision", "Eligible", "Rank", "Score", "Reason", "Date"], rows) : emptyState("No decisions found for this book")}
  `;
}
