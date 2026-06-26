import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { showModal, closeModal } from "../components/modal.js";
import { showBanner } from "../components/banner.js";
import { submitCommand, generateKey } from "../commands.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";

export async function renderRisk() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/risk");
    view.innerHTML = buildRisk(data);
    document.getElementById("halt-btn")?.addEventListener("click", openHaltModal);
    document.getElementById("resume-btn")?.addEventListener("click", openResumeModal);
  } catch (e) {
    view.innerHTML = errorState("Failed to load risk", e.message);
  }
}

function buildRisk(data) {
  const state = data.halted ? "halted" : data.degraded ? "attention" : "ready";
  const haltBtns = data.halted
    ? `<button id="resume-btn" class="btn" style="border-color:var(--aq-positive);color:var(--aq-positive)">Resume</button>`
    : `<button id="halt-btn" class="btn btn-danger">Create Halt</button>`;
  return `
    <div class="card" style="margin-bottom:1rem">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:1rem">
          ${statusChip(state.toUpperCase(), state)}
          ${data.halt_reason ? `<span style="color:var(--aq-negative)">${data.halt_reason}</span>` : ""}
        </div>
        ${haltBtns}
      </div>
    </div>
    <div class="grid-3">
      <div class="card">
        <div class="card-header">Exposure</div>
        ${data.exposure ? `<div>Gross: ${data.exposure.gross}%</div><div>Net: ${data.exposure.net}%</div>` : emptyState("No data")}
      </div>
      <div class="card">
        <div class="card-header">Drawdown</div>
        ${data.drawdown != null ? `${data.drawdown}%` : emptyState("No data")}
      </div>
      <div class="card">
        <div class="card-header">Risk Events</div>
        ${(data.events || []).slice(0, 5).map(e => `<div style="font-size:0.8rem;padding:2px 0">${e.type} — ${fmtDateTime(e.timestamp)}</div>`).join("") || emptyState("No recent events")}
      </div>
    </div>
  `;
}

function openHaltModal() {
  showModal(
    "Create Operational Halt",
    `<p style="color:var(--aq-negative);margin-bottom:0.75rem">This will block decision runs and paper execution.</p>
     <div style="margin-bottom:0.75rem">
       <label class="metric-label">Reason (required)</label>
       <input id="halt-reason" style="display:block;margin-top:4px;width:100%;font-family:var(--aq-font-ui);background:var(--aq-paper);color:var(--aq-ink);border:1px solid var(--aq-rule);border-radius:var(--aq-radius);padding:6px 8px" placeholder="Why is the system halted?">
     </div>`,
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "● Create Halt", class: "btn btn-danger", onclick: executeHalt },
    ],
  );
}

async function executeHalt() {
  const reason = document.getElementById("halt-reason")?.value;
  if (!reason) { showBanner("Halt reason is required.", "blocking"); return; }
  closeModal();
  showBanner("Submitting halt...", "info");
  try {
    const result = await submitCommand("halt.create", {}, {
      idempotency_key: generateKey(),
      book_id: store.bookId,
      reason,
    });
    showBanner(`Halt created: ${result.status}`, "warning");
    await renderRisk();
  } catch (e) {
    showBanner("Halt failed: " + e.message, "blocking");
  }
}

function openResumeModal() {
  showModal(
    "Resume Operations",
    `<p>This will clear the active halt and resume decision runs.</p>
     <div style="margin-bottom:0.75rem">
       <label class="metric-label">Reason (required)</label>
       <input id="resume-reason" style="display:block;margin-top:4px;width:100%;font-family:var(--aq-font-ui);background:var(--aq-paper);color:var(--aq-ink);border:1px solid var(--aq-rule);border-radius:var(--aq-radius);padding:6px 8px" placeholder="Why is the halt being cleared?">
     </div>`,
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "✓ Resume", class: "btn", onclick: executeResume, style: "border-color:var(--aq-positive);color:var(--aq-positive)" },
    ],
  );
}

async function executeResume() {
  const reason = document.getElementById("resume-reason")?.value;
  if (!reason) { showBanner("Resume reason is required.", "blocking"); return; }
  closeModal();
  showBanner("Submitting resume...", "info");
  try {
    const result = await submitCommand("halt.resume", {}, {
      idempotency_key: generateKey(),
      book_id: store.bookId,
      reason,
    });
    showBanner(`Resumed: ${result.status}`, "info");
    await renderRisk();
  } catch (e) {
    showBanner("Resume failed: " + e.message, "blocking");
  }
}
