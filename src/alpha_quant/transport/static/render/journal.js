import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";

export async function renderJournal() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/journal");
    view.innerHTML = buildJournal(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load journal", e.message);
  }
}

function buildJournal(data) {
  const items = data.items || [];
  return `
    <div class="section-header">Journal</div>
    <div class="timeline">
      ${items.length ? items.map(e => `
        <div class="timeline-item ${e.category || ''}">
          <div class="timeline-time">${fmtDateTime(e.timestamp)}</div>
          <div class="timeline-label">${e.category ? `<span class="chip chip-neutral">${e.category}</span> ` : ""}${e.message}</div>
        </div>
      `).join("") : emptyState("No journal entries")}
    </div>
  `;
}
