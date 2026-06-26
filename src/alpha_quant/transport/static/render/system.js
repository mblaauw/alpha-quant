import store from "../state.js";
import { get } from "../api.js";
import { statusChip } from "../components/status.js";
import { errorState } from "../components/error_state.js";

export async function renderSystem() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/system");
    view.innerHTML = buildSystem(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load system", e.message);
  }
}

function buildSystem(data) {
  const components = data.components || {};
  return `
    <div class="section-header">System</div>
    <div style="display:grid;gap:0.5rem;max-width:480px">
      ${Object.entries(components).map(([k, v]) => `
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--aq-rule)">
          <span>${k}</span>
          ${statusChip(v.status || "unknown", v.healthy ? "healthy" : "halted")}
        </div>
      `).join("")}
    </div>
  `;
}
