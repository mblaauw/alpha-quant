import store from "../state.js";
import { get } from "../api.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { tagChip } from "../components/status.js";
import { showModal, closeModal, intro, fieldText, fieldNumber, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import { classify, freshnessFor } from "../freshness.js";
import { openDecisionDrawer } from "./drawers.js";

const COLS = "1.5fr 1fr .6fr .6fr 2.2fr 1.2fr";

export async function renderDecisions() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const bid = store.bookId ? "book_id=" + store.bookId : "";
  const filters = new URLSearchParams(store.filters).toString();
  try {
    const data = await get("/v1/console/decisions?" + (bid ? bid + "&" : "") + filters);
    view.innerHTML = buildDecisions(data);
    wire(data.items || []);
  } catch (e) {
    view.innerHTML = errorState("Failed to load decisions", e.message);
  }
}

window.addEventListener("bookchange", renderDecisions);

function decTone(d) {
  return { enter: "enter", hold: "hold", blocked: "blocked", rejected: "rejected", exclude: "dim" }[d] || "dim";
}

function buildDecisions(data) {
  const header = `<div class="dthead" style="grid-template-columns:${COLS}">
    <span>Symbol</span><span>Decision</span><span class="r-right">Rank</span><span class="r-right">Score</span><span>Reason</span><span class="r-right">Override</span></div>`;

  const rows = (data.items || []).map((d) => {
    const f = d.freshness || freshnessFor(d.symbol) || { age_minutes: null };
    const sev = f.severity || classify(f.age_minutes).severity;
    const blocked = d.decision === "blocked";
    const sevCls = sev === "crit" ? "fresh-badge crit" : sev === "warn" ? "fresh-badge warn" : "fresh-badge";
    const rowCls = blocked ? "dtrow is-stale crit" : "dtrow";
    const actionable = d.decision === "enter" || d.decision === "hold";
    const acts = actionable
      ? `<span class="row-acts"><button class="act-btn approve" data-approve="${d.decision_id || d.symbol}" data-sym="${d.symbol}">Approve</button><button class="act-btn" data-reject="${d.decision_id || d.symbol}" data-sym="${d.symbol}">Reject</button></span>`
      : `<span></span>`;
    return `<div class="${rowCls}" style="grid-template-columns:${COLS}" data-decision="${d.decision_id || d.symbol}">
      <span class="symcell"><span class="sym">${d.symbol}</span><span class="${sevCls}">${sev === "live" ? "LIVE" : "STALE"}</span></span>
      <span>${tagChip(String(d.decision || "").toUpperCase(), decTone(d.decision))}</span>
      <span class="num">${d.rank == null ? "—" : "#" + d.rank}</span>
      <span class="num ink">${d.composite_score != null ? Math.round(d.composite_score * 100) + "%" : "—"}</span>
      <span style="font-size:12px;color:var(--aq-ink2)">${d.reason || "—"}</span>
      ${acts}
    </div>`;
  }).join("");

  return `
    <div class="sec-head"><div class="sec-title">Decision candidates <span class="sub">${data.run_id ? "run " + String(data.run_id).slice(0, 8) : ""}</span></div><span class="sec-note">Blocked rows excluded by the <b>freshness gate</b></span></div>
    ${(data.items || []).length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No decisions for this book")}`;
}

function wire(items) {
  const by = (id) => items.find((d) => (d.decision_id || d.symbol) === id) || {};
  document.querySelectorAll("[data-approve]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); openApprove(by(b.dataset.approve), b.dataset.sym); });
  document.querySelectorAll("[data-reject]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); openReject(by(b.dataset.reject), b.dataset.sym); });
  document.querySelectorAll("[data-decision]").forEach((el) => { el.onclick = () => openDecisionDrawer(el.dataset.decision); });
}

function openApprove(d, sym) {
  showModal("Approve candidate " + sym,
    intro(`Stages a paper order from this decision (rank ${d.rank ?? "—"}, score ${d.composite_score != null ? Math.round(d.composite_score * 100) + "%" : "—"}).`)
      + fieldNumber("a_qty", "Order quantity", 100)
      + fieldText("a_note", "Override note (optional)", "Operator note"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "✓ Approve & stage order", class: "btn btn-go", onclick: () => {
          const qty = parseInt(val("a_qty"), 10) || 100;
          closeModal();
          runWithToast(() => cmd.approve(store.bookId, { decision_id: d.decision_id, symbol: sym, quantity: qty, override_note: val("a_note") || null }, "Approve " + sym), "Approve " + sym, renderDecisions);
        } },
    ]);
}

function openReject(d, sym) {
  showModal("Reject candidate " + sym,
    intro(`Overrides the policy and excludes ${sym} from this run.`)
      + fieldText("rj_reason", "Reason (required)", "Why override?"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "✕ Reject", class: "btn btn-danger", onclick: () => {
          const reason = val("rj_reason"); if (!reason) return;
          closeModal();
          runWithToast(() => cmd.reject(store.bookId, { decision_id: d.decision_id, symbol: sym }, reason), "Reject " + sym, renderDecisions);
        } },
    ]);
}
