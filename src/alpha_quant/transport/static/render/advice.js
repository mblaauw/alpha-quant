import store from "../state.js";
import { get, post } from "../api.js";
import { cmd } from "../commands.js";
import { fmtCurrency, fmtNum } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { runWithToast } from "../components/toast.js";
import { openDrawer } from "../components/drawer.js";

const EQUITY = 350000;
const CASH = 64226;

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s ?? "");
  return d.innerHTML;
}

function cur(v) {
  const a = Math.abs(Math.round(v)).toLocaleString("en-US");
  return (v < 0 ? "-" : "") + "$" + a;
}

function price(v) {
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(v) { return (v * 100).toFixed(2) + "%"; }
function pct1(v) { return (v * 100).toFixed(1) + "%"; }

// ── Sizing engine (mirrors POST /sizing-preview server-side logic) ──

function compute(ticket) {
  const c = ticket.cand;
  const riskBudget = EQUITY * (ticket.riskPct / 100);
  let stopDist, stopBasis;
  if (ticket.method === "atr25") { stopDist = 2.5 * c.atr; stopBasis = "2.5 × ATR " + price(c.atr); }
  else if (ticket.method === "fixed") { stopDist = 0.08 * c.price; stopBasis = "8% × " + price(c.price); }
  else { stopDist = 2.0 * c.atr; stopBasis = "2.0 × ATR " + price(c.atr); }
  const autoQty = Math.max(1, Math.floor(riskBudget / stopDist));
  const qty = ticket.qtyOverride != null ? Math.max(0, ticket.qtyOverride) : autoQty;
  const stopPrice = c.price - stopDist;
  const notional = qty * c.price;
  const riskAtStop = qty * stopDist;
  const target = c.price + 2 * stopDist;
  const targetGain = 2 * riskAtStop;
  const pctEquity = notional / EQUITY;
  const riskPctEquity = riskAtStop / EQUITY;
  const bpAfter = CASH - notional;
  const modified = (ticket.qtyOverride != null && ticket.qtyOverride !== autoQty) || ticket.riskPct !== 0.5 || ticket.method !== "atr20";

  const guards = [];
  if (notional > CASH) guards.push({ sev: "block", icon: "⛔", text: `Notional ${cur(notional)} exceeds buying power $64,226 by ${cur(notional - CASH)}.` });
  if (riskAtStop > EQUITY * 0.01) guards.push({ sev: "warn", icon: "⚠", text: `Risk at stop ${cur(riskAtStop)} is above the 1% per-trade cap ($3,500).` });
  if (pctEquity > 0.20) guards.push({ sev: "warn", icon: "⚠", text: `Notional is ${pct1(pctEquity)} of equity — above 20% single-name guide.` });
  if (qty === 0) guards.push({ sev: "block", icon: "⛔", text: "Quantity is zero — nothing to submit." });
  if (!guards.length) guards.push({ sev: "ok", icon: "✓", text: `Within budget: risk ${cur(riskAtStop)} (${pct(riskPctEquity)}) and notional ${pct1(pctEquity)} of equity pass.` });

  return { c, riskBudget, stopDist, stopBasis, autoQty, qty, stopPrice, notional, riskAtStop, target, targetGain, pctEquity, riskPctEquity, bpAfter, modified, guards, blocked: guards.some(g => g.sev === "block") };
}

function defaultTicket(sym, cand) {
  return { sym, cand, mode: "recommended", riskPct: 0.5, method: "atr20", qtyOverride: null };
}

// ── Advice card ──

function buildCard(c, r) {
  const recMap = { add: "ADD", consider_entry: "CONSIDER ENTRY", hold: "HOLD", reduce: "REDUCE", exit: "EXIT", watch: "WATCH", do_nothing: "—" };
  const recLabel = recMap[c.recommendation] || (c.recommendation || "").toUpperCase();
  return `<div class="acard" data-rec="${c.recommendation}" data-scorecard="${c.scorecard_id}">
    <div class="acard-sym"><span class="s">${esc(c.symbol)}</span></div>
    <div class="acard-mid">
      <div class="acard-rec">
        <span class="rec-chip" data-rec="${c.recommendation}">${recLabel}</span>
        <span class="acard-meta"><b>${Math.round((c.confidence || 0) * 100)}%</b> confidence · score <b>${fmtNum(c.total_score)}</b></span>
      </div>
      <div class="acard-size">Engine size <b>${r.autoQty} sh</b> · ${cur(r.notional)} · risk ${cur(r.riskAtStop)}</div>
    </div>
    <div class="acard-acts-wrap">
      <div class="acard-acts">
        <button class="btn" data-variant="go" data-follow="${c.scorecard_id}">Follow</button>
        <button class="btn" data-sm="true" data-modify="${c.scorecard_id}">Modify</button>
        <button class="btn" data-sm="true" data-variant="danger" data-reject="${c.scorecard_id}">Reject</button>
      </div>
      <a class="acard-detail" data-scorecard-link="${c.scorecard_id}">Full scorecard ›</a>
    </div>
  </div>`;
}

// ── Scorecard drawer (rich M1→M8) ──

function buildScorecardDrawer(s, c) {
  const TYPE_LABEL = { hard: "Hard gate", soft: "Posture", score: "Score", evidence: "Evidence" };
  const ICON = { ok: "✓", info: "●", warn: "⚠", bad: "✕" };

  const modules = (s.modules || []).map(m => {
    const hasScore = m.score != null;
    const barTone = hasScore ? (m.score >= 0.7 ? "up" : m.score >= 0.45 ? "info" : "down") : "";
    return `<div class="dmod" data-type="${esc(m.type || "score")}">
      <div class="dmod-q">${esc(m.question || "")}</div>
      <div class="dmod-head">
        <span class="dmod-id">${esc(m.id || "")}</span>
        <span class="dmod-name">${esc(m.name || "")}</span>
        <span class="dmod-type" data-t="${esc(m.type || "score")}">${esc(TYPE_LABEL[m.type] || m.type || "")}</span>
        <span class="dmod-spacer"></span>
        ${hasScore ? `<span class="dmod-score">${esc(Math.round(m.score * 100) + "%")}</span>` : ""}
        <span class="dmod-state" data-tone="${esc(m.state_tone || "dim")}">${esc(m.state || "")}</span>
      </div>
      ${m.archetype ? `<div class="dmod-archetype">◆ ${esc(m.archetype)}</div>` : ""}
      ${hasScore ? `<div class="dmod-bar"><div class="dmod-bar-fill" data-tone="${barTone}" style="width:${Math.round((m.score || 0) * 100)}%"></div></div>` : ""}
      <div class="dmod-metrics">${(m.metrics || []).map(x => `<span class="dmet">${esc(x.k || "")} <b>${esc(x.v || "")}</b></span>`).join("")}</div>
      <div class="dmod-reason">${esc(m.reason || "")}</div>
    </div>`;
  }).join("");

  const verSev = s.narrative?.severity || "ok";
  const verText = s.narrative?.text || "";
  const verIcon = ICON[verSev] || "●";

  const execution = (s.execution || []).map(e => `<div class="ov-row"><span class="ok">${esc(e.k || "")}</span><span class="ov" data-tone="${esc(e.tone || "")}">${esc(e.v || "")}</span></div>`).join("");
  const portfolio = (s.portfolio_fit || []).map(p => `<div class="ov-row"><span class="ok">${esc(p.k || "")}</span><span class="ov" data-tone="${esc(p.tone || "")}">${esc(p.v || "")}</span></div>`).join("");
  const invals = (s.invalidations || []).map(i => `<li><span class="mk">✕</span><span>${esc(i)}</span></li>`).join("");
  const changed = (s.changed_since || []).map(ch => `<li><span class="mk">→</span><span>${esc(ch)}</span></li>`).join("");

  const r = compute(defaultTicket(c.symbol, c));

  return `<div class="dw-stats">
    <div class="statblock"><span class="sl">Composite</span><span class="sv">${fmtNum(s.total_score)}</span><span class="ss">${esc(s.score_scale || "")}</span></div>
    <div class="statblock"><span class="sl">Evidence align</span><span class="sv">${s.evidence_alignment ?? "—"}/100</span><span class="ss">calibration: ${esc(s.calibration || "provisional")}</span></div>
    <div class="statblock"><span class="sl">Data quality</span><span class="sv" data-tone="${s.data_quality === "warn" ? "warn" : s.data_quality === "fail" ? "down" : "up"}">${esc((s.data_quality || "pass").toUpperCase())}</span><span class="ss">point-in-time</span></div>
    <div class="statblock"><span class="sl">Rank</span><span class="sv">${esc(s.rank || "—")}</span><span class="ss">eligible set</span></div>
  </div>
  ${verText ? `<div class="verdict" data-sev="${verSev}"><span class="vi">${verIcon}</span><span>${esc(verText)}</span></div>` : ""}
  ${modules ? `<div class="dw-sechead"><span class="t">Decision hierarchy</span><span class="n">M1 → M8</span></div>
  <div class="tax-legend">
    <span class="tax-item"><span class="tax-dot" data-t="hard"></span>Hard gate — blocks</span>
    <span class="tax-item"><span class="tax-dot" data-t="soft"></span>Posture — modifies size</span>
    <span class="tax-item"><span class="tax-dot" data-t="score"></span>Score — ranks</span>
    <span class="tax-item"><span class="tax-dot" data-t="evidence"></span>Evidence — explains</span>
  </div>${modules}` : ""}
  ${execution ? `<div class="dw-sechead"><span class="t">Execution plan</span><span class="n">conditional</span></div><div class="ov-grid">${execution}</div>` : ""}
  ${portfolio ? `<div class="dw-sechead"><span class="t">Portfolio fit</span></div><div class="ov-grid">${portfolio}</div>` : ""}
  ${invals ? `<div class="dw-sechead"><span class="t">What invalidates this</span></div><ul class="dlist" data-kind="inval">${invals}</ul>` : ""}
  ${changed ? `<div class="dw-sechead"><span class="t">Changed since last run</span></div><ul class="dlist" data-kind="changed">${changed}</ul>` : ""}
  <div class="dw-foot">
    <div class="left"><button class="btn" data-variant="danger" data-dw-reject="${c.scorecard_id}">Reject</button></div>
    <div class="right">
      <button class="btn" data-sm="true" data-dw-modify="${c.scorecard_id}">Modify…</button>
      <button class="btn" data-variant="go" data-dw-follow="${c.scorecard_id}">Follow — ${r.autoQty} sh</button>
    </div>
  </div>`;
}

// ── Order ticket ──

function buildTicket(ticket) {
  const r = compute(ticket);
  const c = r.c;
  const lock = ticket.mode !== "modify";
  const recLabel = ticket.recLabel || "";
  const tk = {
    symbol: c.symbol, recLabel,
    recommendedOn: ticket.mode !== "modify", modifyOn: ticket.mode === "modify", lockControls: lock,
    qty: String(r.qty), autoQty: String(r.autoQty),
    sizeTag: r.modified ? "Modified" : "Engine sized", modified: r.modified,
    riskBudget: cur(r.riskBudget), riskPct: ticket.riskPct.toFixed(2) + "%", riskPctRaw: ticket.riskPct,
    stopDist: price(r.stopDist), stopBasis: r.stopBasis,
    stopPrice: price(r.stopPrice), stopPct: "−" + pct1(r.stopDist / c.price),
    qtyNote: ticket.qtyOverride != null && ticket.qtyOverride !== r.autoQty ? " → overridden to " + r.qty : "",
    notional: cur(r.notional), pctEquity: pct1(r.pctEquity),
    riskAtStop: cur(r.riskAtStop), riskPctEquity: pct(r.riskPctEquity),
    riskTone: r.riskAtStop > EQUITY * 0.01 ? "warn" : "",
    target: price(r.target), targetGain: cur(r.targetGain),
    bpAfter: cur(r.bpAfter), bpTone: r.bpAfter < 0 ? "down" : "", price: price(c.price),
    m20: ticket.method === "atr20", m25: ticket.method === "atr25", mfix: ticket.method === "fixed",
    qtyAutoNote: ticket.qtyOverride != null && ticket.qtyOverride !== r.autoQty ? "Manual override." : "Following engine size.",
    qtyAutoAction: ticket.qtyOverride != null && ticket.qtyOverride !== r.autoQty ? "Reset to " + r.autoQty : "",
    submitLabel: r.blocked ? "Blocked by guardrail" : (r.modified ? "Submit modified — " + r.qty + " sh" : "Follow — submit " + r.qty + " sh"),
    submitDisabled: r.blocked,
  };

  return `<div class="tk-head">
    <div class="tt"><span class="tk-title">${esc(c.symbol)} <span class="rec-chip" data-rec="${c.rec}">${recLabel}</span></span><span class="tk-sub">market order · paper book</span></div>
    <button class="tk-close" id="tk-close-btn">✕</button>
  </div>
  <div class="tk-body">
    <div class="mode-toggle">
      <button data-on="${tk.recommendedOn}" id="tk-rec-mode">Recommended</button>
      <button data-on="${tk.modifyOn}" id="tk-mod-mode">Modify</button>
    </div>
    <div class="size-hero">
      <div class="size-hero-top">
        <div class="size-qty">${tk.qty}<small>shares</small></div>
        <span class="size-tag" data-mod="${tk.modified}">${tk.sizeTag}</span>
      </div>
      <div class="size-math">Risk budget <b>${tk.riskBudget}</b> <span class="op">=</span> ${tk.riskPct} of <b>${cur(EQUITY)}</b><br>
        Stop distance <b>${tk.stopDist}</b> <span class="op">=</span> ${tk.stopBasis}<br>
        Shares <span class="op">=</span> ${tk.riskBudget} <span class="op">÷</span> ${tk.stopDist} <span class="op">=</span> <b>${tk.autoQty}</b>${tk.qtyNote}</div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Per-trade risk budget</span><span class="v">${tk.riskPct} · ${tk.riskBudget}</span></div>
      <input type="range" class="rng" min="0.25" max="1" step="0.05" value="${tk.riskPctRaw}" ${lock ? "disabled" : ""} id="tk-risk">
      <div class="rng-ticks"><span>0.25%</span><span>0.50%</span><span>0.75%</span><span>1.00%</span></div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Stop method</span><span class="v">stop @ ${tk.stopPrice}</span></div>
      <div class="seg">
        <button data-on="${tk.m20}" ${lock ? "disabled" : ""} id="tk-m20">ATR 2.0×</button>
        <button data-on="${tk.m25}" ${lock ? "disabled" : ""} id="tk-m25">ATR 2.5×</button>
        <button data-on="${tk.mfix}" ${lock ? "disabled" : ""} id="tk-fix">Fixed 8%</button>
      </div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Quantity</span><span class="v">${tk.notional} notional</span></div>
      <div class="qty-row">
        <div class="qty-stepper">
          <button ${lock ? "disabled" : ""} id="tk-qty-minus">−</button>
          <input type="number" value="${tk.qty}" ${lock ? "disabled" : ""} id="tk-qty">
          <button ${lock ? "disabled" : ""} id="tk-qty-plus">+</button>
        </div>
        <span class="qty-auto">${tk.qtyAutoNote} ${tk.qtyAutoAction ? `<a id="tk-reset-qty">${tk.qtyAutoAction}</a>` : ""}</span>
      </div>
    </div>
    <div class="tk-metrics">
      <div class="tk-metric"><div class="ml">Notional</div><div class="mv">${tk.notional}</div><div class="ms">${tk.pctEquity} of equity</div></div>
      <div class="tk-metric"><div class="ml">Stop price</div><div class="mv">${tk.stopPrice}</div><div class="ms">−${tk.stopDist} (${tk.stopPct})</div></div>
      <div class="tk-metric"><div class="ml">Risk at stop</div><div class="mv" data-tone="${tk.riskTone}">${tk.riskAtStop}</div><div class="ms">${tk.riskPctEquity} of equity · 1R</div></div>
      <div class="tk-metric"><div class="ml">Target 2R</div><div class="mv" data-tone="up">${tk.target}</div><div class="ms">+${tk.targetGain} if hit</div></div>
      <div class="tk-metric"><div class="ml">Buying power after</div><div class="mv" data-tone="${tk.bpTone}">${tk.bpAfter}</div><div class="ms">from $64,226</div></div>
      <div class="tk-metric"><div class="ml">Avg cost basis</div><div class="mv">${tk.price}</div><div class="ms">last Lake mark</div></div>
    </div>
    ${r.guards.map(g => `<div class="guard" data-sev="${g.sev}"><span class="gi">${g.icon}</span><span>${esc(g.text)}</span></div>`).join("")}
  </div>
  <div class="tk-foot">
    <div class="left"><button class="btn" data-variant="danger" id="tk-reject">Reject advice</button></div>
    <div class="right">
      <button class="btn" id="tk-cancel">Cancel</button>
      <button class="btn" data-variant="primary" ${tk.submitDisabled ? "disabled" : ""} id="tk-submit">${tk.submitLabel}</button>
    </div>
  </div>`;
}

// ── State ──

let _candCache = [];
let _activeTicket = null;
let _scorecardCache = {};

// ── Main render ──

export async function renderAdvice() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/advice/today?book_id=" + (store.bookId || ""));
    _candCache = data.items || [];
    view.innerHTML = buildPage(data);
    wire(data.items || []);
  } catch (e) {
    view.innerHTML = errorState("Failed to load advice", e.message);
  }
}

window.addEventListener("bookchange", renderAdvice);

function buildPage(data) {
  const items = data.items || [];
  if (!items.length) return emptyState("No advice for today. Run a decision cycle first.") + `<div style="text-align:center;margin-top:16px"><button class="btn btn-primary" onclick="document.getElementById('run-btn').click()">Run decision cycle</button></div>`;

  const cards = items.map(i => {
    const c = { symbol: i.symbol, name: "", rec: i.recommendation, price: 100, atr: 3.3 };
    const r = compute(defaultTicket(i.symbol, c));
    return buildCard(i, r);
  }).join("");

  return `<div class="metric-strip">
    <div class="metric"><span class="metric-label">Open positions</span><span class="metric-value">6</span></div>
    <div class="metric"><span class="metric-label">Gross exposure</span><span class="metric-value">$285,774</span><span class="metric-sub">82% of equity</span></div>
    <div class="metric"><span class="metric-label">Buying power</span><span class="metric-value">$64,226</span><span class="metric-sub">cash available</span></div>
    <div class="metric"><span class="metric-label">Today's risk used</span><span class="metric-value">0.0%</span><span class="metric-sub">of 2.0% daily cap</span></div>
  </div>
  <div class="sec-head"><div class="sec-title">Today's advice — portfolio actions</div><span class="sec-sub">${items.length} actionable · latest run</span></div>
  ${cards}`;
}

function wire(items) {
  document.querySelectorAll("[data-scorecard-link], [data-scorecard]").forEach(el => {
    el.addEventListener("click", async (e) => {
      if (e.target.closest("[data-follow]") || e.target.closest("[data-modify]") || e.target.closest("[data-reject]")) return;
      const id = el.dataset.scorecardLink || el.dataset.scorecard;
      await openScorecard(id);
    });
  });

  document.querySelectorAll("[data-follow]").forEach(b => {
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = b.dataset.follow;
      const item = items.find(i => i.scorecard_id === id);
      if (!item) return;
      await openTicket(item, "recommended");
    });
  });

  document.querySelectorAll("[data-modify]").forEach(b => {
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = b.dataset.modify;
      const item = items.find(i => i.scorecard_id === id);
      if (!item) return;
      await openTicket(item, "modify");
    });
  });

  document.querySelectorAll("[data-reject]").forEach(b => {
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = b.dataset.reject;
      const item = items.find(i => i.scorecard_id === id);
      if (!item) return;
      doReject(item);
    });
  });
}

async function openScorecard(scorecardId) {
  const item = _candCache.find(i => i.scorecard_id === scorecardId);
  if (!item) return;

  let sc = _scorecardCache[scorecardId];
  if (!sc) {
    try {
      sc = await get(`/v1/console/scorecards/${scorecardId}`);
      _scorecardCache[scorecardId] = sc;
    } catch (e) {
      openDrawer("Scorecard", `<div class="error-state"><div class="error-state-title">Failed to load</div><div class="error-state-detail">${esc(e.message)}</div></div>`);
      return;
    }
  }

  const c = { symbol: item.symbol, name: "", rec: item.recommendation, price: 100, atr: 3.3 };
  const body = buildScorecardDrawer(sc, c);
  openDrawer(`${esc(item.symbol)} <span class="rec-chip" data-rec="${item.recommendation}">${esc((item.recommendation || "").toUpperCase())}</span>`, body);
  openDrawer(document.getElementById("drawer-title")?.textContent || "", body);

  document.querySelector("[data-dw-reject]")?.addEventListener("click", () => { closeDrawer(); doReject(item); });
  document.querySelector("[data-dw-modify]")?.addEventListener("click", () => { closeDrawer(); openTicket(item, "modify"); });
  document.querySelector("[data-dw-follow]")?.addEventListener("click", () => { closeDrawer(); openTicket(item, "recommended"); });
}

async function openTicket(item, mode) {
  let sizing;
  try {
    sizing = await post("/v1/console/sizing-preview", {
      book_id: store.bookId,
      symbol: item.symbol,
      side: "buy",
    });
  } catch {
    sizing = { suggested_qty: 100, last_price: 100, atr: 3.3, stop_price: 94, stop_distance: 6, risk_budget: 1750, notional: 10000, risk_at_stop: 600, buying_power: 63000, buying_power_after: 53000, guardrails: [] };
  }

  const c = { symbol: item.symbol, name: "", rec: item.recommendation, price: sizing.last_price || 100, atr: sizing.atr || 3.3 };
  const recLabel = (item.recommendation || "").toUpperCase();
  _activeTicket = { sym: item.symbol, cand: c, recLabel, mode: mode || "recommended", riskPct: 0.5, method: "atr20", qtyOverride: null, scorecardId: item.scorecard_id };

  renderTicket();
  wireTicket();
}

function renderTicket() {
  const el = document.getElementById("tk-overlay");
  const overlay = el || document.createElement("div");
  if (!el) {
    overlay.id = "tk-overlay";
    overlay.className = "tk-overlay";
    overlay.innerHTML = `<div class="ticket" id="ticket">${buildTicket(_activeTicket)}</div>`;
    document.body.appendChild(overlay);
  } else {
    overlay.querySelector("#ticket").innerHTML = buildTicket(_activeTicket);
  }
  overlay.dataset.open = "true";
}

function wireTicket() {
  const close = () => { document.getElementById("tk-overlay").dataset.open = "false"; _activeTicket = null; };
  document.getElementById("tk-close-btn")?.addEventListener("click", close);
  document.getElementById("tk-cancel")?.addEventListener("click", close);
  document.getElementById("tk-overlay")?.addEventListener("click", (e) => { if (e.target === e.currentTarget) close(); });

  document.getElementById("tk-rec-mode")?.addEventListener("click", () => { _activeTicket.mode = "recommended"; _activeTicket.riskPct = 0.5; _activeTicket.method = "atr20"; _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });
  document.getElementById("tk-mod-mode")?.addEventListener("click", () => { _activeTicket.mode = "modify"; renderTicket(); wireTicket(); });

  document.getElementById("tk-risk")?.addEventListener("input", (e) => { _activeTicket.riskPct = parseFloat(e.target.value); _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });
  document.getElementById("tk-m20")?.addEventListener("click", () => { _activeTicket.method = "atr20"; _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });
  document.getElementById("tk-m25")?.addEventListener("click", () => { _activeTicket.method = "atr25"; _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });
  document.getElementById("tk-fix")?.addEventListener("click", () => { _activeTicket.method = "fixed"; _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });

  document.getElementById("tk-qty")?.addEventListener("input", (e) => { const v = parseInt(e.target.value, 10); _activeTicket.qtyOverride = isNaN(v) ? 0 : v; renderTicket(); wireTicket(); });
  document.getElementById("tk-qty-minus")?.addEventListener("click", () => { _activeTicket.qtyOverride = Math.max(0, (parseInt(_activeTicket.qtyOverride ?? compute(_activeTicket).autoQty, 10) || 0) - 1); renderTicket(); wireTicket(); });
  document.getElementById("tk-qty-plus")?.addEventListener("click", () => { _activeTicket.qtyOverride = (parseInt(_activeTicket.qtyOverride ?? compute(_activeTicket).autoQty, 10) || 0) + 1; renderTicket(); wireTicket(); });
  document.getElementById("tk-reset-qty")?.addEventListener("click", () => { _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });

  document.getElementById("tk-submit")?.addEventListener("click", () => {
    const r = compute(_activeTicket);
    if (r.blocked) return;
    const isMod = _activeTicket.qtyOverride != null || _activeTicket.riskPct !== 0.5 || _activeTicket.method !== "atr20";
    const bookId = store.bookId;
    const reason = "Order from Desk";
    if (isMod) {
      runWithToast(() => cmd.modify(bookId, { scorecard_id: _activeTicket.scorecardId, qty: r.qty, stop_price: r.stopPrice, risk_pct: _activeTicket.riskPct / 100, method: _activeTicket.method }, reason), "Submit modified — " + _activeTicket.sym);
    } else {
      runWithToast(() => cmd.approve(bookId, { scorecard_id: _activeTicket.scorecardId, qty: r.qty, symbol: _activeTicket.sym }, reason), "Follow — " + _activeTicket.sym);
    }
    close();
  });

  document.getElementById("tk-reject")?.addEventListener("click", () => { const item = _candCache.find(i => i.scorecard_id === _activeTicket?.scorecardId); if (item) doReject(item); close(); });
}

function doReject(item) {
  const reason = prompt("Reason for rejecting " + item.symbol + "?", "Operator override");
  if (!reason) return;
  runWithToast(() => cmd.reject(store.bookId, { scorecard_id: item.scorecard_id }, reason), "Reject — " + item.symbol);
}

function closeDrawer() {
  const overlay = document.getElementById("drawer-overlay");
  const drawer = document.getElementById("drawer");
  if (overlay) overlay.classList.remove("open");
  if (drawer) drawer.classList.remove("open");
}
