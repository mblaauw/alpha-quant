import { get } from "../api.js";
import { cmd } from "../commands.js";
import { fmtCurrency, fmtNum } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { showModal, closeModal } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { openDrawer as showDrawer } from "../components/drawer.js";
import store from "../state.js";

export async function renderAdvice() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/advice/today");
    view.innerHTML = buildAdvicePage(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load advice", e.message);
  }
}

function buildAdvicePage(data) {
  const items = data.items || [];
  if (!items.length) return emptyState("No advice for today. Run a decision cycle first.") + `
    <div style="text-align:center;margin-top:16px">
      <button class="btn btn-primary" onclick="document.getElementById('run-btn').click()">Run decision cycle</button>
    </div>`;

  const actions = items.filter(i => i.recommendation === "add" || i.recommendation === "consider_entry" || i.recommendation === "reduce" || i.recommendation === "exit");
  const neutral = items.filter(i => i.recommendation === "hold" || i.recommendation === "watch");
  const nothing = items.filter(i => i.recommendation === "do_nothing");

  return `
    <div class="sec-head" style="margin-bottom:16px">
      <h2 style="margin:0;font-family:var(--aq-serif);font-weight:600">Today's Advice</h2>
      <span class="age">${items.length} symbols — ${fmtDate(items[0]?.run_date)}</span>
    </div>

    ${actions.length ? buildSection("Portfolio actions", "Symbols requiring attention", actions, true) : ""}
    ${neutral.length ? buildSection("Portfolio overview", "Symbols on watch", neutral, false) : ""}
    ${nothing.length ? buildSection("No action needed", "Symbols with do-nothing recommendation", nothing, false) : ""}
  `;
}

function buildSection(title, subtitle, items, actionable) {
  return `
    <div class="card" style="margin-bottom:16px">
      <div class="card-head" style="margin-bottom:12px">${title} <span class="age">${subtitle}</span></div>
      ${items.map(i => buildCard(i, actionable)).join("")}
    </div>`;
}

function buildCard(item, actionable) {
  const rec = item.recommendation || "do_nothing";
  const chipColor = rec === "add" || rec === "consider_entry" ? "var(--aq-up)"
    : rec === "reduce" || rec === "exit" ? "var(--aq-down)"
    : rec === "hold" ? "var(--aq-blue)"
    : "var(--aq-ink3)";
  const conf = Math.round((item.confidence || 0) * 100);
  const quality = item.data_quality || "pass";
  const qualityBadge = quality === "fail" ? `<span class="fresh-badge crit">POOR DATA</span>`
    : quality === "warn" ? `<span class="fresh-badge warn">PARTIAL DATA</span>`
    : "";

  return `
    <div class="kv" style="align-items:stretch;padding:12px;margin-bottom:8px;background:var(--aq-bg2);border-radius:var(--aq-radius);cursor:pointer"
         onclick="window._adviceEvidence('${item.scorecard_id}')">
      <span class="symcell" style="flex:1">
        <span class="d" style="width:8px;height:8px;border-radius:50%;background:${chipColor};flex-shrink:0"></span>
        <span class="sym" style="font-weight:600">${item.symbol}</span>
        <span style="font-size:12px;padding:1px 6px;border-radius:3px;background:${chipColor}22;color:${chipColor}">${rec.toUpperCase()}</span>
        <span class="age" style="font-size:11px">${conf}% confidence · Score ${fmtNum(item.total_score)}</span>
        ${qualityBadge}
      </span>
      <span style="display:inline-flex;gap:4px;flex-shrink:0">
        ${actionable ? `
          <button class="btn btn-sm" style="font-size:11px" onclick="event.stopPropagation();window._adviceFollow('${item.symbol}','${item.scorecard_id}',${item.total_score})">Follow</button>
          <button class="btn btn-sm" style="font-size:11px" onclick="event.stopPropagation();window._adviceReject('${item.symbol}','${item.scorecard_id}')">Reject</button>
        ` : ""}
        <button class="btn btn-sm" style="font-size:11px" onclick="event.stopPropagation();window._adviceEvidence('${item.scorecard_id}')">Details</button>
      </span>
    </div>`;
}

function fmtDate(raw) {
  if (!raw) return "";
  try { return new Date(raw).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" }); }
  catch { return raw; }
}

window._adviceFollow = function(symbol, scorecardId, totalScore) {
  const bookId = store.bookId;
  const qty = Math.round(1000); // default size
  showModal(
    `Follow advice — ${symbol}`,
    `<p style="margin:0 0 12px;font-size:14px;color:var(--aq-ink2)">Submit a market order for ${symbol} based on scorecard recommendation.</p>
     <div class="kv"><span class="l">Symbol</span><span class="r">${symbol}</span></div>
     <div class="kv"><span class="l">Score</span><span class="r">${fmtNum(totalScore)}</span></div>
     <div class="kv"><span class="l">Quantity</span><span class="r">${qty}</span></div>`,
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Submit order", class: "btn btn-primary", onclick: () => {
        closeModal();
        runWithToast(
          () => cmd.submit("candidate.follow", { symbol, decision_id: scorecardId, quantity: qty }, bookId),
          `Follow advice — ${symbol}`,
        );
      }},
    ],
  );
};

window._adviceReject = function(symbol, scorecardId) {
  const bookId = store.bookId;
  showModal(
    `Reject advice — ${symbol}`,
    `<p style="margin:0 0 12px;font-size:14px;color:var(--aq-ink2)">This will record your override and leave the position unchanged.</p>
     <label style="display:block;margin-bottom:4px;font-size:12px;color:var(--aq-ink2)">Reason</label>
     <input id="reject-reason" class="fld" placeholder="Why are you rejecting this advice?" style="width:100%">`,
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Reject", class: "btn btn-sm", style: "background:var(--aq-down-soft);color:var(--aq-down)", onclick: () => {
        const reason = document.getElementById("reject-reason")?.value || "Operator rejected";
        closeModal();
        runWithToast(
          () => cmd.submit("candidate.reject", { decision_id: scorecardId }, bookId, reason),
          `Reject advice — ${symbol}`,
        );
      }},
    ],
  );
};

window._adviceEvidence = async function(scorecardId) {
  try {
    const sc = await get(`/v1/console/scorecards/${scorecardId}`);
    const comps = (sc.components || []).map(c => `
      <div class="kv">
        <span class="l">${c.name}</span>
        <span class="r" style="color:${c.passed ? "var(--aq-up)" : "var(--aq-down)"}">${fmtNum(c.score)}${c.passed ? "" : " — FAIL"}</span>
      </div>
      <div class="age" style="padding-left:12px;margin-bottom:6px;font-size:11px">${c.reason || ""}</div>
    `).join("");
    showDrawer(
      `${sc.symbol} — ${sc.recommendation.toUpperCase()}`,
      `<div class="kv-grid" style="grid-template-columns:1fr 1fr">
        <div><div class="metric-value" style="font-size:18px">${fmtNum(sc.total_score)}</div><div class="metric-label">Total score</div></div>
        <div><div class="metric-value" style="font-size:18px">${Math.round((sc.confidence || 0) * 100)}%</div><div class="metric-label">Confidence</div></div>
      </div>
      <div style="margin-top:16px">
        <div class="sec-head" style="margin-bottom:8px"><div class="card-head" style="margin:0">Components</div></div>
        ${comps || emptyState("No component data")}
      </div>`
    );
  } catch (e) {
    showDrawer("Evidence", `<p class="age">Failed to load scorecard: ${e.message}</p>`);
  }
};
