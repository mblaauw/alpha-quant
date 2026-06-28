import { get } from "../api.js";
import { openDrawer } from "../components/drawer.js";
import { showModal, closeModal, intro, fieldNumber, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import store from "../state.js";
import { fmtCurrency, fmtPrice, fmtDateTime, esc } from "../formatters.js";

function statBlock(label, value, tone) {
  return `<div class="statblock"><span class="metric-label">${esc(label)}</span><span class="metric-value" data-tone="${tone || ""}">${value}</span></div>`;
}

function provLine(label, value, tone) {
  const cls = tone === "snap" ? 'style="color:var(--aq-snap)"' : tone === "pv" ? 'class="pv"' : 'class="pl"';
  return `<div class="provline"><span class="pl">${esc(label)}</span><span ${cls}>${value}</span></div>`;
}

function fillRow(f) {
  const side = (f.side || "").toLowerCase();
  const sideTone = side === "sell" || side === "reject" ? "sell" : "buy";
  return `<div class="frow" data-side="${sideTone}">
    <div class="f-main"><span class="f-side" data-side="${sideTone}">${esc(f.side || "")}</span><span class="f-qty">${esc(f.qty)}</span><span class="f-price">@ ${esc(f.price)}</span></div>
    <span class="f-extra">${esc(f.slippage_bps ? "slip " + f.slippage_bps + " bps" : f.note || "")}</span>
    <span class="f-when">${esc(f.ts ? fmtDateTime(f.ts) : f.when || "")}</span>
  </div>`;
}

export async function openPositionDrawer(positionId) {
  try {
    const data = await get(`/v1/console/positions/${encodeURIComponent(positionId)}`);
    const pos = data.position || data;
    const mv = pos.market_value || 0;
    const pl = pos.unrealized_pl || 0;
    const stats = [
      statBlock("Qty", esc(pos.quantity)),
      statBlock("Avg cost", fmtPrice(pos.avg_cost)),
      statBlock("Price", fmtPrice(pos.current_price)),
      statBlock("Mkt value", fmtCurrency(mv)),
      statBlock("Unreal. P&L", fmtCurrency(pl), pl >= 0 ? "up" : "down"),
    ].join("");

    const comps = (data.scorecard?.components || data.components || []).map((c) =>
      `<div><div class="comp-row"><span class="comp-name">${esc(c.name)}</span><span class="comp-score" data-tone="${c.tone || "dim"}">${esc(c.score)}</span></div><div class="comp-reason">${esc(c.reason || "")}</div></div>`
    ).join("");

    const fills = (data.fills || []).map(fillRow).join("");

    const stopDistPct = pos.stop_price && pos.current_price
      ? (((pos.current_price - pos.stop_price) / pos.current_price) * 100).toFixed(1) + "% below"
      : "—";

    const body = `
      <div class="dr-stats">${stats}</div>
      ${comps ? `<div class="dr-section"><div class="dr-sechead"><span class="t">Today's advice</span><span class="n">scorecard ${pos.scorecard_id || ""}</span></div><div class="dr-card">${comps}</div></div>` : ""}
      <div class="dr-section"><div class="dr-sechead"><span class="t">Risk method</span><span class="n">METHOD_REGISTRY</span></div><div class="dr-card">
        ${provLine("Active method", "ATR trail 2.0×", "pv")}
        ${provLine("Current stop", pos.stop_price ? fmtPrice(pos.stop_price) : "—")}
        ${provLine("Distance to stop", stopDistPct)}
        ${provLine("Open risk (R)", "+1.3 R")}
        <div class="method-pick">
          <span class="method-opt" data-on="true">ATR trail 2.0×</span>
          <span class="method-opt">Fixed %</span>
          <span class="method-opt">Time stop 30d</span>
          <span class="method-opt">Drawdown ladder</span>
        </div>
      </div></div>
      ${fills ? `<div class="dr-section"><div class="dr-sechead"><span class="t">Fills that built this position</span><span class="n">${data.fills.length} fills</span></div><div class="dr-card"><div class="trace">${fills}</div></div></div>` : ""}
      <div class="dr-actions">
        <button class="btn" id="dr-edit-stop">Edit stop</button>
        <button class="btn" data-variant="danger" id="dr-flatten">Flatten position</button>
      </div>`;

    const title = `${esc(pos.symbol || positionId)} <span class="chip" data-tone="${pl >= 0 ? "ok" : "dim"}">${pl >= 0 ? "OPEN" : "LOSS"}</span>`;
    openDrawer(title, body);

    document.getElementById("dr-edit-stop")?.addEventListener("click", () => {
      openStopModal(pos);
    });
    document.getElementById("dr-flatten")?.addEventListener("click", () => {
      runWithToast(() => cmd.flatten(store.bookId, pos.position_id || positionId, "Flatten from drawer"), "Flatten " + (pos.symbol || positionId));
    });
  } catch (e) {
    openDrawer("Position", `<div class="error-state"><div class="error-state-title">Failed to load</div><div class="error-state-detail">${esc(e.message)}</div></div>`);
  }
}

export async function openOrderDrawer(orderId) {
  try {
    const data = await get(`/v1/console/orders/${encodeURIComponent(orderId)}`);
    const sideTone = data.side === "sell" ? "bad" : "ok";
    const statusTone = data.status === "filled" ? "ok" : data.status === "pending" ? "warn" : data.status === "rejected" ? "bad" : "dim";
    const stats = [
      statBlock("Side", (data.side || "—").toUpperCase(), sideTone),
      statBlock("Requested", esc(data.requested_qty ?? "—")),
      statBlock("Filled", esc(data.filled_qty ?? "—")),
      statBlock("Status", (data.status || "—").toUpperCase(), statusTone),
    ].join("");

    const fills = (data.fills || []).map(fillRow).join("");

    const body = `
      <div class="dr-stats">${stats}</div>
      <div class="dr-section"><div class="dr-sechead"><span class="t">Order intent</span></div><div class="dr-card">
        ${provLine("Side / type", (data.side || "—") + " · " + (data.type || "market"))}
        ${provLine("Requested qty", String(data.requested_qty ?? "—"))}
        ${provLine("Filled qty", String(data.filled_qty ?? "—"))}
        ${provLine("Avg fill price", data.avg_fill_price ? fmtPrice(data.avg_fill_price) : "—")}
        ${provLine("Reason", esc(data.reason || ""))}
      </div></div>
      ${fills ? `<div class="dr-section"><div class="dr-sechead"><span class="t">Fill trace</span><span class="n">${data.fills.length} fills</span></div><div class="dr-card"><div class="trace">${fills}</div></div></div>` : ""}
      <div class="dr-section"><div class="dr-sechead"><span class="t">Provenance</span></div><div class="dr-card">
        ${provLine("Decision", data.provenance?.decision_id ? data.provenance.decision_id.slice(0, 10) : "—", "pv")}
        ${provLine("Run", data.provenance?.run_id ? data.provenance.run_id.slice(0, 10) : "—", "pv")}
        ${provLine("Snapshot", data.provenance?.snapshot_id || "—", "snap")}
      </div></div>
      ${(data.status || "").toLowerCase() === "pending" ? `<div class="dr-actions"><button class="btn" data-variant="danger" id="dr-cancel">Cancel order</button></div>` : ""}`;

    const title = `${esc(data.symbol || "Order")} <span class="chip" data-tone="${statusTone}">${(data.status || "").toUpperCase()}</span>`;
    openDrawer(title, body);

    document.getElementById("dr-cancel")?.addEventListener("click", () => {
      runWithToast(() => cmd.orderCancel(store.bookId, data.order_id, "Cancelled from drawer"), "Cancel " + (data.order_id || "").slice(0, 8));
    });
  } catch (e) {
    openDrawer("Order", `<div class="error-state"><div class="error-state-title">Failed to load</div><div class="error-state-detail">${esc(e.message)}</div></div>`);
  }
}

export async function openDecisionDrawer(decisionId) {
  try {
    const data = await get(`/v1/console/decisions/${encodeURIComponent(decisionId)}`);
    const dec = data.decision || data;
    const blocked = dec.blocked;
    const sev = blocked ? "bad" : "ok";
    const verdictSev = data.narrative?.severity || sev;
    const verdictText = data.narrative?.text || (blocked ? "Blocked: " + (dec.block_reason || "gate failed") : "Score " + (dec.composite_score ?? "—"));
    const verdictIcon = verdictSev === "ok" ? "✓" : verdictSev === "warn" ? "⚠" : "✕";

    const modules = (data.modules || []).map((m) =>
      `<div class="mrow" data-type="${esc(m.type || "score")}">
        <span class="mrow-id">${esc(m.id || "")}</span>
        <span class="mrow-mid"><span class="mrow-name">${esc(m.name || "")}</span><span class="mrow-reason">${esc(m.reason || "")}</span></span>
        <span class="mrow-r">${m.score != null ? `<span class="mrow-score">${esc(m.score)}</span>` : ""}<span class="mrow-state" data-tone="${esc(m.state_tone || "dim")}">${esc(m.state || "")}</span></span>
      </div>`
    ).join("");

    const stats = [
      statBlock("Decision", (dec.decision || dec.block_reason || "—").toUpperCase(), blocked ? "down" : "up"),
      statBlock("Composite", dec.composite_score != null ? (Math.round(dec.composite_score * 100) + "%") : "—"),
      statBlock("Regime", esc(dec.regime || "—")),
    ].join("");

    const posNow = data.position_now || "No position";
    const openRisk = data.open_risk || "Not evaluated";

    const body = `
      <div class="dverdict" data-sev="${verdictSev}">
        <span class="dvi">${verdictIcon}</span>
        <span><span class="dvk">Desk interpretation</span>${esc(verdictText)}</span>
      </div>
      <div class="dr-stats" style="grid-template-columns:repeat(3,1fr);margin-bottom:12px;padding-bottom:12px">${stats}</div>
      ${modules ? `
      <div class="dr-section"><div class="dr-sechead"><span class="t">Decision hierarchy</span><span class="n">M1 → M8</span></div>
      <div class="tax-legend">
        <span class="tax-item"><span class="tax-dot" data-t="hard"></span>Hard gate</span>
        <span class="tax-item"><span class="tax-dot" data-t="soft"></span>Posture</span>
        <span class="tax-item"><span class="tax-dot" data-t="score"></span>Score</span>
        <span class="tax-item"><span class="tax-dot" data-t="evidence"></span>Evidence</span>
      </div>
      <div class="dr-card" style="padding-top:4px;padding-bottom:4px">${modules}</div></div>` : ""}
      <div class="dr-section"><div class="dr-sechead"><span class="t">Position &amp; outcome</span></div><div class="dr-card">
        ${provLine("Decision", (dec.decision || "—").toUpperCase())}
        ${provLine("Position now", esc(posNow))}
        ${provLine("Open risk · stop", esc(openRisk))}
      </div></div>
      <div class="dr-section"><div class="dr-sechead"><span class="t">Act on this decision</span></div>
      <div class="act-grid">
        ${!blocked ? `<button class="btn" data-variant="go" id="dr-approve">Approve</button>` : ""}
        <button class="btn" id="dr-hold">Hold</button>
        <button class="btn" id="dr-reduce">Reduce ½</button>
        <button class="btn" data-variant="danger" id="dr-exit">Exit position</button>
        <button class="btn act-full" id="dr-stop">Edit stop</button>
      </div></div>`;

    const title = `${esc(dec.symbol || decisionId)} <span class="chip" data-tone="${sev}">${blocked ? "BLOCKED" : "ACTIVE"}</span>`;
    openDrawer(title, body);

    document.getElementById("dr-approve")?.addEventListener("click", () => runWithToast(() => cmd.approve(store.bookId, { decision_id: dec.candidate_id, symbol: dec.symbol }, "Approve from drawer"), "Approve " + dec.symbol));
    document.getElementById("dr-hold")?.addEventListener("click", () => runWithToast(() => cmd.approve(store.bookId, { decision_id: dec.candidate_id, symbol: dec.symbol }, "Hold from drawer"), "Hold " + dec.symbol));
    document.getElementById("dr-reduce")?.addEventListener("click", () => runWithToast(() => cmd.approve(store.bookId, { decision_id: dec.candidate_id, symbol: dec.symbol, quantity: 0 }, "Reduce from drawer"), "Reduce " + dec.symbol));
    document.getElementById("dr-exit")?.addEventListener("click", () => runWithToast(() => cmd.flatten(store.bookId, dec.symbol, "Exit from drawer"), "Exit " + dec.symbol));
    document.getElementById("dr-stop")?.addEventListener("click", () => runWithToast(() => cmd.setStop(store.bookId, dec.symbol, 0, "Stop update from drawer"), "Edit stop — " + dec.symbol));
  } catch (e) {
    openDrawer("Decision", `<div class="error-state"><div class="error-state-title">Failed to load</div><div class="error-state-detail">${esc(e.message)}</div></div>`);
  }
}

export async function openRunDrawer(runId) {
  try {
    const data = await get(`/v1/console/runs/${encodeURIComponent(runId)}`);
    const run = data.run || data;
    const steps = (run.pipeline_steps || data.steps || []).map((s, i) => {
      const tone = (s.status || "").includes("✓") ? "buy" : "";
      return `<div class="frow" data-side="${tone || "reject"}">
        <div class="f-main"><span class="f-qty" style="font-size:12px;font-weight:600">${esc(s.name || "Step " + (i + 1))}</span></div>
        <span class="f-extra">${esc(s.status || "")}</span>
        <span class="f-when">${esc(s.detail || "")}</span>
      </div>`;
    }).join("");

    const stats = [
      statBlock("Type", (run.run_kind || run.type || "—").toUpperCase()),
      statBlock("Candidates", String(run.candidates_evaluated ?? run.candidates ?? data.decisions?.length ?? "—")),
      statBlock("Status", (run.status || "—").toUpperCase()),
    ].join("");

    const body = `
      <div class="dr-stats" style="grid-template-columns:repeat(3,1fr)">${stats}</div>
      ${steps ? `<div class="dr-section"><div class="dr-sechead"><span class="t">Pipeline timeline</span></div><div class="dr-card"><div class="trace">${steps}</div></div></div>` : ""}
      <div class="dr-section"><div class="dr-sechead"><span class="t">Provenance</span></div><div class="dr-card">
        ${provLine("Snapshot", data.snapshot || run.snapshot || "—", "snap")}
        ${provLine("Config sha", data.sha || run.sha || "—")}
      </div></div>`;

    const statusTone = run.status === "completed" ? "ok" : run.status === "running" ? "warn" : "dim";
    const title = `${esc((run.run_id || runId || "").slice(0, 10))} <span class="chip" data-tone="${statusTone}">${esc(run.status || "")}</span>`;
    openDrawer(title, body);
  } catch (e) {
    openDrawer("Run", `<div class="error-state"><div class="error-state-title">Failed to load</div><div class="error-state-detail">${esc(e.message)}</div></div>`);
  }
}

function openStopModal(pos) {
  const sym = pos.symbol || "";
  const currentStop = pos.stop_price || "";
  showModal("Edit stop — " + sym,
    fieldNumber("st_price", "Stop price", currentStop),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Update stop", class: "btn btn-primary", onclick: () => {
          const px = parseFloat(val("st_price"));
          if (!px) return;
          closeModal();
          runWithToast(() => cmd.setStop(store.bookId, pos.position_id || sym, px, "Stop update from drawer"), sym + " stop " + px);
        } },
    ]);
}

