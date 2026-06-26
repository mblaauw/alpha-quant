import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";

export async function renderJournal() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
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
    <div class="sec-head"><div class="sec-title">Journal <span class="sub">immutable event timeline</span></div></div>
    <div class="timeline">
      ${items.length ? items.map((e) => `
        <div class="tl-item ${e.category || ""}">
          <div class="tl-time"><span>${fmtDateTime(e.timestamp)}</span>${e.category ? `<span class="cat">${e.category}</span>` : ""}</div>
          <div class="tl-msg">${e.message}</div>
        </div>`).join("") : emptyState("No journal entries")}
    </div>`;
}
