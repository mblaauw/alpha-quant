import store from "../state.js";
import { get } from "../api.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { statusChip } from "../components/status.js";
import { classify, ageLabel } from "../freshness.js";

export async function renderSystem() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/system");
    view.innerHTML = buildSystem(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load system", e.message);
  }
}

function buildSystem(data) {
  const components = data.components || {};
  const compRows = Object.entries(components).map(([k, v]) =>
    `<div class="kv"><span><span class="l">${k}</span>${v.detail ? `<span class="de" style="display:block;font-family:var(--aq-mono);font-size:10.5px;color:var(--aq-ink3)">${v.detail}</span>` : ""}</span>${statusChip((v.status || "unknown").toUpperCase(), v.healthy ? "healthy" : "halted")}</div>`).join("");

  const fr = store.freshness || {};
  const feed = (fr.symbols || []).map((s) => {
    const sev = s.severity || classify(s.age_minutes).severity;
    const stale = sev !== "live";
    const color = sev === "crit" ? "var(--aq-down)" : sev === "warn" ? "var(--aq-amber)" : "var(--aq-up)";
    const badge = sev === "crit" ? "fresh-badge crit" : sev === "warn" ? "fresh-badge warn" : "fresh-badge";
    return `<div class="kv" style="opacity:${stale ? ".62" : "1"}">
      <span class="symcell"><span class="d" style="width:7px;height:7px;border-radius:50%;background:${color}"></span><span class="sym">${s.symbol}</span><span class="sym-name">${s.name || ""}</span></span>
      <span style="display:inline-flex;align-items:center;gap:6px"><span class="age" style="color:${stale ? color : "var(--aq-ink3)"}">${ageLabel(s.age_minutes)}</span><span class="${badge}">${stale ? "STALE" : "LIVE"}</span></span>
    </div>`;
  }).join("");

  return `
    <div class="grid-2">
      <div>
        <div class="sec-title" style="margin-bottom:13px">Components</div>
        <div class="card">${compRows || emptyState("No components reported")}</div>
      </div>
      <div>
        <div class="sec-title" style="margin-bottom:13px">Lake feed detail</div>
        <div class="card">${feed || emptyState("Freshness endpoint not available")}</div>
      </div>
    </div>`;
}
