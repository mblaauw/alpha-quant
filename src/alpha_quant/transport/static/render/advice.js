import store from "../state.js";
import { get, post } from "../api.js";
import { cmd } from "../commands.js";
import { fmtCurrency, fmtNum, esc } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { runWithToast } from "../components/toast.js";
import { openDrawer, closeDrawer } from "../components/drawer.js";

function price(v) {
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct1(v) { return (v * 100).toFixed(1) + "%"; }

// ── State ──

let _candCache = [];
let _activeTicket = null;
let _ticketSizing = null;
let _scorecardCache = {};

// ── Advice card ──

function buildCard(c) {
  const recMap = { add: "ADD", consider_entry: "CONSIDER ENTRY", hold: "HOLD", reduce: "REDUCE", exit: "EXIT", watch: "WATCH", do_nothing: "NO ACTION" };
  const recLabel = recMap[c.recommendation] || (c.recommendation || "").toUpperCase();
  const engSize = c.suggested_qty ? `Engine size <b>${c.suggested_qty} sh</b> · ${fmtCurrency(c.notional)} · risk ${fmtCurrency(c.risk_at_stop)}` : "";
  const conf = Math.round((c.confidence || 0) * 100);
  const thesis = c.thesis || `${recLabel} — confidence ${conf}%, score ${fmtNum(c.total_score)}${c.suggested_qty ? `, engine sizes ${c.suggested_qty} sh` : ""}.`;

  return `<div class="acard" data-rec="${c.recommendation}" data-scorecard="${c.scorecard_id}">
    <div class="acard-sym"><span class="s">${esc(c.symbol)}</span>${c.name ? `<span class="n">${esc(c.name)}</span>` : ""}</div>
    <div class="acard-mid">
      <div class="acard-rec">
        <span class="rec-chip" data-rec="${c.recommendation}">${recLabel}</span>
        <span class="acard-meta"><b>${conf}%</b> confidence · score <b>${fmtNum(c.total_score)}</b></span>
      </div>
      <div class="acard-thesis">${esc(thesis)}</div>
      ${engSize ? `<div class="acard-size">${engSize}</div>` : ""}
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

function buildScorecardDrawer(s) {
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
        ${hasScore ? `<span class="dmod-score">${esc(m.score.toFixed(2))}</span>` : ""}
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
    <div class="left"><button class="btn" data-variant="danger" data-dw-reject="${s.scorecard_id}">Reject</button></div>
    <div class="right">
      <button class="btn" data-sm="true" data-dw-modify="${s.scorecard_id}">Modify…</button>
      <button class="btn" data-variant="go" data-dw-follow="${s.scorecard_id}">Follow</button>
    </div>
  </div>`;
}

// ── Helpers ──

function recLabel(rec) {
  const m = { add: "ADD", consider_entry: "CONSIDER ENTRY", hold: "HOLD", reduce: "REDUCE", exit: "EXIT", watch: "WATCH", do_nothing: "NO ACTION" };
  return m[rec] || (rec || "").toUpperCase();
}

const RISK_PCT_FRAC = 0.005; // 0.5%

function _qtyGuardrails(qty, sizing, equity) {
  const notional = qty * sizing.last_price;
  const riskAtStop = qty * sizing.stop_distance;
  const bpAfter = sizing.buying_power - notional;
  const guards = [];
  if (notional > sizing.buying_power) {
    guards.push({ severity: "block", icon: "⛔", message: `Notional ${fmtCurrency(notional)} exceeds buying power ${fmtCurrency(sizing.buying_power)} by ${fmtCurrency(notional - sizing.buying_power)}.` });
  }
  if (riskAtStop > equity * 0.01) {
    guards.push({ severity: "warn", icon: "⚠", message: `Risk at stop ${fmtCurrency(riskAtStop)} is above the 1% per-trade cap (${fmtCurrency(equity * 0.01)}).` });
  }
  if (notional > equity * 0.20) {
    guards.push({ severity: "warn", icon: "⚠", message: `Notional ${pct1(notional / equity)} of equity — above 20% single-name guide.` });
  }
  if (qty === 0) {
    guards.push({ severity: "block", icon: "⛔", message: "Quantity is zero — nothing to submit." });
  }
  if (!guards.length) {
    guards.push({ severity: "ok", icon: "✓", message: `Within budget: risk ${fmtCurrency(riskAtStop)} (${pct1(riskAtStop / equity)}) and notional ${pct1(notional / equity)} of equity pass.` });
  }
  return guards;
}

// ── Ticket build ──

function buildTicket(ticket, sizing) {
  const lock = ticket.mode !== "modify";
  const equity = sizing.equity || 350000;
  const qty = ticket.qtyOverride != null ? ticket.qtyOverride : sizing.suggested_qty;
  const notional = qty * sizing.last_price;
  const riskAtStop = qty * sizing.stop_distance;
  const bpAfter = sizing.buying_power - notional;
  const targetPrice = sizing.last_price + 2 * sizing.stop_distance;
  const targetGain = 2 * riskAtStop;
  const guards = _qtyGuardrails(qty, sizing, equity);
  const blocked = guards.some(g => g.severity === "block");
  const isMod = ticket.mode === "modify" && (ticket.qtyOverride != null || ticket.riskPct !== 0.5 || ticket.method !== "atr_2_0");

  return `<div class="tk-head">
    <div class="tt"><span class="tk-title">${esc(ticket.sym)} <span class="rec-chip" data-rec="${ticket.rec}">${esc(ticket.recLabel)}</span></span><span class="tk-sub">${esc(ticket.name || ticket.sym)} · market order · paper book</span></div>
    <button class="tk-close" id="tk-close-btn">✕</button>
  </div>
  <div class="tk-body">
    <div class="mode-toggle">
      <button data-on="${ticket.mode === "recommended"}" id="tk-rec-mode">Recommended</button>
      <button data-on="${ticket.mode === "modify"}" id="tk-mod-mode">Modify</button>
    </div>
    <div class="size-hero">
      <div class="size-hero-top">
        <div class="size-qty">${qty}<small>shares</small></div>
        <span class="size-tag" data-mod="${isMod}">${isMod ? "Modified" : "Engine sized"}</span>
      </div>
      <div class="size-math">Risk budget <b>${fmtCurrency(sizing.risk_budget)}</b> <span class="op">=</span> ${pct1(ticket.riskPct / 100)} of <b>${fmtCurrency(equity)}</b><br>
        Stop distance <b>${price(sizing.stop_distance)}</b> <span class="op">=</span> ${sizing.stop_basis || ticket.method.replace(/_/g, " ").toUpperCase()}<br>
        Shares <span class="op">=</span> ${fmtCurrency(sizing.risk_budget)} <span class="op">÷</span> ${price(sizing.stop_distance)} <span class="op">=</span> <b>${sizing.suggested_qty}</b></div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Per-trade risk budget</span><span class="v">${pct1(ticket.riskPct / 100)} · ${fmtCurrency(sizing.risk_budget)}</span></div>
      <input type="range" class="rng" min="0.25" max="1" step="0.05" value="${ticket.riskPct}" ${lock ? "disabled" : ""} id="tk-risk">
      <div class="rng-ticks"><span>0.25%</span><span>0.50%</span><span>0.75%</span><span>1.00%</span></div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Stop method</span><span class="v">stop @ ${price(sizing.stop_price)}</span></div>
      <div class="seg">
        <button data-on="${ticket.method === "atr_2_0"}" ${lock ? "disabled" : ""} id="tk-m20">ATR 2.0×</button>
        <button data-on="${ticket.method === "atr_2_5"}" ${lock ? "disabled" : ""} id="tk-m25">ATR 2.5×</button>
        <button data-on="${ticket.method === "fixed_8"}" ${lock ? "disabled" : ""} id="tk-fix">Fixed 8%</button>
      </div>
    </div>
    <div class="ctrl-block">
      <div class="ctrl-label"><span class="l">Quantity</span><span class="v">${fmtCurrency(notional)} notional</span></div>
      <div class="qty-row">
        <div class="qty-stepper">
          <button ${lock ? "disabled" : ""} id="tk-qty-minus">−</button>
          <input type="number" value="${qty}" ${lock ? "disabled" : ""} id="tk-qty">
          <button ${lock ? "disabled" : ""} id="tk-qty-plus">+</button>
        </div>
        <span class="qty-auto">${ticket.qtyOverride != null ? "Manual override. " : "Following engine size. "}${ticket.qtyOverride != null ? `<a id="tk-reset-qty">Reset to ${sizing.suggested_qty}</a>` : ""}</span>
      </div>
    </div>
    <div class="tk-metrics">
      <div class="tk-metric"><div class="ml">Notional</div><div class="mv">${fmtCurrency(notional)}</div><div class="ms">${pct1(notional / equity)} of equity</div></div>
      <div class="tk-metric"><div class="ml">Stop price</div><div class="mv">${price(sizing.stop_price)}</div><div class="ms">−${price(sizing.stop_distance)} (${pct1(sizing.stop_distance / sizing.last_price)})</div></div>
      <div class="tk-metric"><div class="ml">Risk at stop</div><div class="mv" data-tone="${riskAtStop > equity * 0.01 ? "warn" : ""}">${fmtCurrency(riskAtStop)}</div><div class="ms">${pct1(riskAtStop / equity)} of equity · 1R</div></div>
      <div class="tk-metric"><div class="ml">Target 2R</div><div class="mv" data-tone="up">${price(targetPrice)}</div><div class="ms">+${fmtCurrency(targetGain)} if hit</div></div>
      <div class="tk-metric"><div class="ml">Buying power after</div><div class="mv" data-tone="${bpAfter < 0 ? "down" : ""}">${fmtCurrency(bpAfter)}</div><div class="ms">from ${fmtCurrency(sizing.buying_power)}</div></div>
      <div class="tk-metric"><div class="ml">Avg cost basis</div><div class="mv">${price(sizing.last_price)}</div><div class="ms">last Lake mark</div></div>
    </div>
    ${guards.map(g => `<div class="guard" data-sev="${g.severity}"><span class="gi">${g.icon}</span><span>${esc(g.message)}</span></div>`).join("")}
  </div>
  <div class="tk-foot">
    <div class="left"><button class="btn" data-variant="danger" id="tk-reject">Reject advice</button></div>
    <div class="right">
      <button class="btn" id="tk-cancel">Cancel</button>
      <button class="btn" data-variant="primary" ${blocked ? "disabled" : ""} id="tk-submit">${blocked ? "Blocked by guardrail" : (isMod ? "Submit modified — " + qty + " sh" : "Follow — submit " + qty + " sh")}</button>
    </div>
  </div>`;
}

// ── Main render ──

export async function renderAdvice() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const bid = store.bookId ? "?book_id=" + store.bookId : "";
  try {
    const [advice, portfolio] = await Promise.all([
      get("/v1/console/advice/today" + bid),
      get("/v1/console/portfolio" + bid).catch(() => null),
    ]);
    _candCache = advice.items || [];
    view.innerHTML = buildPage(advice, portfolio);
    wire(advice.items || []);
  } catch (e) {
    view.innerHTML = errorState("Failed to load advice", e.message);
  }
}

window.addEventListener("bookchange", renderAdvice);

function buildPage(data, portfolio) {
  const items = data.items || [];
  if (!items.length) return emptyState("No advice for today. Run a decision cycle first.") + `<div style="text-align:center;margin-top:16px"><button class="btn btn-primary" onclick="document.getElementById('run-btn').click()">Run decision cycle</button></div>`;
  const cards = items.map(i => buildCard(i)).join("");

  const p = portfolio || {};
  const posCount = p.positions_count || items.length;
  const eq = p.equity || 350000;
  const ge = p.gross_exposure || (p.equity ? p.equity * 0.82 : 285774);
  const gePct = eq > 0 ? ((ge / eq) * 100).toFixed(1) : "—";

  return `<div class="metric-strip">
    <div class="metric"><span class="metric-label">Open positions</span><span class="metric-value">${posCount}</span></div>
    <div class="metric"><span class="metric-label">Gross exposure</span><span class="metric-value">${fmtCurrency(ge)}</span><span class="metric-sub">${gePct}% of equity</span></div>
    <div class="metric"><span class="metric-label">Buying power</span><span class="metric-value">${fmtCurrency(p.cash || 64226)}</span><span class="metric-sub">cash available</span></div>
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

  const body = buildScorecardDrawer(sc);
  const subtitle = `${item.name || item.symbol} · scorecard ${scorecardId.slice(0, 8)} · policy v4 · latest run`;
  openDrawer(`${esc(item.symbol)} <span class="rec-chip" data-rec="${item.recommendation}">${esc(recLabel(item.recommendation))}</span>`, body, subtitle);

  document.querySelector("[data-dw-reject]")?.addEventListener("click", () => { closeDrawer(); doReject(item); });
  document.querySelector("[data-dw-modify]")?.addEventListener("click", () => { closeDrawer(); openTicket(item, "modify"); });
  document.querySelector("[data-dw-follow]")?.addEventListener("click", () => { closeDrawer(); openTicket(item, "recommended"); });
}

async function openTicket(item, mode) {
  _ticketSizing = null;
  const params = {
    book_id: store.bookId,
    symbol: item.symbol,
    side: "buy",
    risk_pct: RISK_PCT_FRAC,
    method: "atr_2_0",
  };
  _activeTicket = {
    sym: item.symbol, name: item.name || "", rec: item.recommendation, recLabel: recLabel(item.recommendation),
    mode: mode || "recommended", riskPct: 0.5, method: "atr_2_0", qtyOverride: null,
    scorecardId: item.scorecard_id,
  };

  renderTicket();
  wireTicket();

  try {
    await fetchSizing(params);
  } catch (_e) {
    _ticketSizing = null;
    renderTicket();
    wireTicket();
    return;
  }
  renderTicket();
  wireTicket();
}

async function fetchSizing(params) {
  const res = await post("/v1/console/sizing-preview", params);
  _ticketSizing = res;
  return res;
}

function renderTicket() {
  const el = document.getElementById("tk-overlay");
  const overlay = el || document.createElement("div");
  if (!el) {
    overlay.id = "tk-overlay";
    overlay.className = "tk-overlay";
    document.body.appendChild(overlay);
  }
  if (!_ticketSizing) {
    overlay.innerHTML = `<div class="ticket" style="text-align:center;padding:40px"><div class="skeleton" style="height:200px"></div></div>`;
  } else {
    overlay.innerHTML = `<div class="ticket" id="ticket">${buildTicket(_activeTicket, _ticketSizing)}</div>`;
  }
  overlay.dataset.open = "true";
}

function wireTicket() {
  const close = () => { document.getElementById("tk-overlay").dataset.open = "false"; _activeTicket = null; _ticketSizing = null; };
  document.getElementById("tk-close-btn")?.addEventListener("click", close);
  document.getElementById("tk-cancel")?.addEventListener("click", close);
  document.getElementById("tk-overlay")?.addEventListener("click", (e) => { if (e.target === e.currentTarget) close(); });

  document.getElementById("tk-rec-mode")?.addEventListener("click", async () => {
    _activeTicket.mode = "recommended"; _activeTicket.riskPct = 0.5; _activeTicket.method = "atr_2_0"; _activeTicket.qtyOverride = null;
    try { await fetchSizing({ book_id: store.bookId, symbol: _activeTicket.sym, side: "buy", risk_pct: RISK_PCT_FRAC, method: "atr_2_0" }); } catch {}
    renderTicket(); wireTicket();
  });
  document.getElementById("tk-mod-mode")?.addEventListener("click", () => { _activeTicket.mode = "modify"; renderTicket(); wireTicket(); });

  document.getElementById("tk-risk")?.addEventListener("input", async (e) => {
    _activeTicket.riskPct = parseFloat(e.target.value); _activeTicket.qtyOverride = null;
    try { await fetchSizing({ book_id: store.bookId, symbol: _activeTicket.sym, side: "buy", risk_pct: _activeTicket.riskPct / 100, method: _activeTicket.method }); } catch {}
    renderTicket(); wireTicket();
  });
  document.getElementById("tk-m20")?.addEventListener("click", async () => {
    _activeTicket.method = "atr_2_0"; _activeTicket.qtyOverride = null;
    try { await fetchSizing({ book_id: store.bookId, symbol: _activeTicket.sym, side: "buy", risk_pct: _activeTicket.riskPct / 100, method: "atr_2_0" }); } catch {}
    renderTicket(); wireTicket();
  });
  document.getElementById("tk-m25")?.addEventListener("click", async () => {
    _activeTicket.method = "atr_2_5"; _activeTicket.qtyOverride = null;
    try { await fetchSizing({ book_id: store.bookId, symbol: _activeTicket.sym, side: "buy", risk_pct: _activeTicket.riskPct / 100, method: "atr_2_5" }); } catch {}
    renderTicket(); wireTicket();
  });
  document.getElementById("tk-fix")?.addEventListener("click", async () => {
    _activeTicket.method = "fixed_8"; _activeTicket.qtyOverride = null;
    try { await fetchSizing({ book_id: store.bookId, symbol: _activeTicket.sym, side: "buy", risk_pct: _activeTicket.riskPct / 100, method: "fixed_8" }); } catch {}
    renderTicket(); wireTicket();
  });

  document.getElementById("tk-qty")?.addEventListener("input", (e) => { const v = parseInt(e.target.value, 10); _activeTicket.qtyOverride = isNaN(v) ? 0 : v; renderTicket(); wireTicket(); });
  document.getElementById("tk-qty-minus")?.addEventListener("click", () => { _activeTicket.qtyOverride = Math.max(0, (_activeTicket.qtyOverride ?? _ticketSizing?.suggested_qty ?? 0) - 1); renderTicket(); wireTicket(); });
  document.getElementById("tk-qty-plus")?.addEventListener("click", () => { _activeTicket.qtyOverride = (_activeTicket.qtyOverride ?? _ticketSizing?.suggested_qty ?? 0) + 1; renderTicket(); wireTicket(); });
  document.getElementById("tk-reset-qty")?.addEventListener("click", () => { _activeTicket.qtyOverride = null; renderTicket(); wireTicket(); });

  document.getElementById("tk-submit")?.addEventListener("click", () => {
    if (!_ticketSizing) return;
    const qty = _activeTicket.qtyOverride ?? _ticketSizing.suggested_qty;
    const equity = _ticketSizing.equity || 350000;
    const riskAtStop = qty * _ticketSizing.stop_distance;
    const notional = qty * _ticketSizing.last_price;
    const blocked = notional > _ticketSizing.buying_power || riskAtStop > equity * 0.01 || qty === 0;
    if (blocked) return;
    const isMod = _activeTicket.qtyOverride != null || _activeTicket.riskPct !== 0.5 || _activeTicket.method !== "atr_2_0";
    const bookId = store.bookId;
    const reason = "Order from Desk";
    if (isMod) {
      runWithToast(() => cmd.modify(bookId, {
        scorecard_id: _activeTicket.scorecardId, symbol: _activeTicket.sym,
        qty, stop_price: _ticketSizing.stop_price,
        risk_pct: _activeTicket.riskPct / 100, method: _activeTicket.method,
      }, reason), "Submit modified — " + _activeTicket.sym);
    } else {
      runWithToast(() => cmd.approve(bookId, {
        scorecard_id: _activeTicket.scorecardId, symbol: _activeTicket.sym,
        quantity: qty,
      }, reason), "Follow — " + _activeTicket.sym);
    }
    close();
  });

  document.getElementById("tk-reject")?.addEventListener("click", () => { const item = _candCache.find(i => i.scorecard_id === _activeTicket?.scorecardId); if (item) doReject(item); close(); });
}

function doReject(item) {
  runWithToast(
    () => cmd.reject(store.bookId, { scorecard_id: item.scorecard_id }, "Operator override"),
    "Reject advice — " + item.symbol,
  );
}
