import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { tagChip } from "../components/status.js";
import { showModal, closeModal, intro, fieldText, fieldSelect, fieldDateTime, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import { openRunDrawer } from "./drawers.js";

const COLS = "1.2fr 1fr 1fr 1fr 1fr .7fr .5fr";

export async function renderRuns() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const bid = store.bookId ? "?book_id=" + store.bookId : "";
  try {
    const data = await get("/v1/console/runs" + bid);
    view.innerHTML = buildRuns(data);
    document.getElementById("bt-btn").onclick = openBacktest;
    document.querySelectorAll("[data-run]").forEach((el) => { el.onclick = () => openRunDrawer(el.dataset.run); });
  } catch (e) {
    view.innerHTML = errorState("Failed to load runs", e.message);
  }
}

window.addEventListener("bookchange", renderRuns);

function buildRuns(data) {
  const header = `<div class="dthead" style="grid-template-columns:${COLS}">
    <span>Run ID</span><span>Type</span><span>Status</span><span>Started</span><span>Completed</span><span class="r-right">Cand.</span><span></span></div>`;
  const rows = (data.items || []).map((r) => `
    <div class="dtrow" style="grid-template-columns:${COLS}" data-run="${r.run_id}">
      <span class="age" style="font-size:11px;color:var(--aq-ink2)">${(r.run_id || "").slice(0, 10)}</span>
      <span>${tagChip((r.run_type || r.run_kind || "").toUpperCase(), r.run_kind === "decision" ? "decision" : "dim")}</span>
      <span>${tagChip((r.status || "").toUpperCase(), r.status)}</span>
      <span class="age" style="font-size:11px">${fmtDateTime(r.started_at)}</span>
      <span class="age" style="font-size:11px">${fmtDateTime(r.completed_at)}</span>
      <span class="num">${r.candidates_evaluated ?? "—"}</span>
      <span class="chev">›</span>
    </div>`).join("");

  return `
    <div class="sec-head"><div class="sec-title">Runs <span class="sub">decisions · backtests · replays</span></div><button id="bt-btn" class="run-btn">+ Backtest / replay</button></div>
    ${(data.items || []).length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No runs yet")}`;
}

function openBacktest() {
  showModal("Trigger backtest / replay",
    intro("Runs the policy over a historical window using point-in-time Lake snapshots — deterministic and reproducible.")
      + fieldSelect("bt_kind", "Run kind", ["backtest", "replay", "shadow"])
      + fieldDateTime("bt_from", "From")
      + fieldDateTime("bt_to", "To")
      + fieldText("bt_snap", "Snapshot pin", "e.g. market-close-2026-06-24"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Queue run", class: "btn btn-primary", onclick: () => {
          const payload = {
            run_kind: val("bt_kind"),
            from: val("bt_from") ? new Date(val("bt_from")).toISOString() : null,
            to: val("bt_to") ? new Date(val("bt_to")).toISOString() : null,
            snapshot_id: val("bt_snap") || null,
          };
          closeModal();
          runWithToast(() => cmd.backtest(store.bookId, payload, "Backtest from Desk"), payload.run_kind + " run", renderRuns);
        } },
    ]);
}
