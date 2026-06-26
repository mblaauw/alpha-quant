import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { tagChip } from "../components/status.js";
import { showModal, closeModal, intro, fieldText, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";

export async function renderRisk() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/risk");
    view.innerHTML = buildRisk(data);
    const h = document.getElementById("halt-btn"); if (h) h.onclick = openHalt;
    const r = document.getElementById("resume-btn"); if (r) r.onclick = openResume;
  } catch (e) {
    view.innerHTML = errorState("Failed to load risk", e.message);
  }
}

function buildRisk(data) {
  const state = data.halted ? "halted" : data.degraded ? "attention" : "ready";
  const btn = data.halted
    ? `<button id="resume-btn" class="btn btn-go">✓ Resume operations</button>`
    : `<button id="halt-btn" class="btn btn-danger">● Create halt</button>`;
  const ex = data.exposure || {};
  const events = (data.events || []).map((e) => {
    const color = e.severity === "critical" ? "var(--aq-down)" : e.severity === "warning" ? "var(--aq-amber)" : "var(--aq-up)";
    return `<div class="event"><span class="d" style="background:${color}"></span><span><span class="ty">${e.type}</span><span class="de">${e.detail || ""}${e.timestamp ? " · " + fmtDateTime(e.timestamp) : ""}</span></span></div>`;
  }).join("");

  return `
    <div class="risk-head">
      <div style="display:flex;align-items:center;gap:13px">${tagChip(state.toUpperCase(), state)}${data.halt_reason ? `<span style="color:var(--aq-down);font-size:13px">${data.halt_reason}</span>` : ""}</div>
      ${btn}
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-head">Exposure</div>
        <div class="kv"><span class="l">Gross</span><span class="mono" style="font-weight:700">${ex.gross != null ? ex.gross + "%" : "—"}</span></div>
        <div class="kv"><span class="l">Net</span><span class="mono" style="font-weight:700">${ex.net != null ? ex.net + "%" : "—"}</span></div>
        <div class="kv"><span class="l">Cap</span><span class="mono" style="color:var(--aq-ink3)">${ex.cap != null ? ex.cap + "%" : "90%"}</span></div>
      </div>
      <div class="card"><div class="card-head">Drawdown</div>
        <div class="bigstat">${data.drawdown != null ? data.drawdown + "%" : "—"}</div>
        <div class="metric-sub" style="margin-top:8px">peak-to-trough · limit ${data.drawdown_limit ?? "-10"}%</div>
      </div>
      <div class="card"><div class="card-head">Risk events</div>${events || emptyState("No recent events")}</div>
    </div>`;
}

function openHalt() {
  showModal("Create operational halt",
    intro("Blocks all decision runs and paper execution until cleared.", true)
      + fieldText("halt_reason", "Reason (required)", "Why is the system halted?"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "● Create halt", class: "btn btn-danger", onclick: () => {
          const reason = val("halt_reason"); if (!reason) return;
          closeModal(); runWithToast(() => cmd.haltCreate(store.bookId, reason), "Create halt", renderRisk);
        } },
    ]);
}

function openResume() {
  showModal("Resume operations",
    intro("Clears the active halt and re-enables runs and execution.")
      + fieldText("resume_reason", "Reason (required)", "Why is the halt cleared?"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "✓ Resume", class: "btn btn-go", onclick: () => {
          const reason = val("resume_reason"); if (!reason) return;
          closeModal(); runWithToast(() => cmd.haltResume(store.bookId, reason), "Resume operations", renderRisk);
        } },
    ]);
}
