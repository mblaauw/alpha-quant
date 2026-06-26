import { get } from "../api.js";
import { fmtCurrency, fmtNum, fmtDateTime } from "../formatters.js";
import { statusChip, tagChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { classify, ageLabel } from "../freshness.js";
import store from "../state.js";

export async function renderDesk() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/desk");
    view.innerHTML = buildDesk(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load desk", e.message);
  }
}

function buildDesk(data) {
  const p = data.portfolio || {};
  const fr = store.freshness || {};
  const stale = fr.stale_count || 0;
  const staleList = (fr.symbols || []).filter((s) => (s.severity || classify(s.age_minutes).severity) !== "live").map((s) => s.symbol);

  const metrics = [
    metric("Equity", fmtCurrency(p.equity), "paper book"),
    metric("Cash", fmtCurrency(p.cash), "available"),
    metric("Gross exposure", fmtCurrency(p.gross_exposure), p.equity ? Math.round((p.gross_exposure / p.equity) * 100) + "% of equity" : ""),
    metric("Unrealized P&L", fmtCurrency(p.unrealized_pl), "open positions", p.unrealized_pl >= 0 ? "up" : "down"),
    metric("Positions", fmtNum(p.positions_count), stale ? stale + " on stale data" : "all fresh"),
    metric("Pending commands", fmtNum(data.pending_commands), "in flight"),
  ].join("");

  return `
    <div class="metric-strip">${metrics}</div>
    <div class="grid-2" style="margin-bottom:14px">
      <div class="card"><div class="card-head">Operational readiness</div>${buildReadiness(data)}</div>
      <div class="card"><div class="card-head">Latest decision run</div>${buildLatestRun(data)}</div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-head">Attention queue</div>${buildAttention(data, fr)}</div>
      <div class="card">
        <div class="sec-head" style="margin-bottom:12px"><div class="card-head" style="margin:0">Lake feed freshness</div><span class="age">${(fr.fresh_count ?? "—")} fresh · ${stale} stale</span></div>
        ${buildFeed(fr)}
      </div>
    </div>`;
}

function metric(label, value, sub, tone = "") {
  return `<div class="metric"><span class="metric-label">${label}</span><span class="metric-value ${tone}">${value}</span><span class="metric-sub">${sub || ""}</span></div>`;
}

function buildReadiness(data) {
  const checks = data.health_checks || {};
  const rows = Object.entries(checks).map(([k, v]) =>
    `<div class="kv"><span class="l">${k}</span>${statusChip((v.status || "").toUpperCase(), v.healthy ? "healthy" : "halted")}</div>`).join("");
  return rows || emptyState("No checks reported");
}

function buildLatestRun(data) {
  const r = data.last_run;
  if (!r) return emptyState("No run yet");
  return `
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">${statusChip((r.status || "").toUpperCase(), r.status)}<span class="age" style="font-size:12px">${fmtDateTime(r.completed_at || r.started_at)}</span></div>
    <div class="kv-grid" style="grid-template-columns:1fr 1fr">
      <div><div class="metric-value" style="font-size:20px">${r.candidates_evaluated ?? 0}</div><div class="metric-label">Candidates</div></div>
      <div><div class="metric-value" style="font-size:20px;color:var(--aq-up)">${r.entries ?? 0}</div><div class="metric-label">Entries</div></div>
    </div>
    <div style="margin-top:13px;padding-top:11px;border-top:1px solid var(--aq-rule)" class="age">Snapshot — ${r.snapshot_id || "live"}</div>`;
}

function buildAttention(data, fr) {
  const items = [];
  if (data.halted) items.push(att("var(--aq-down)", "System halted — " + (data.halt_reason || "no reason given")));
  (fr.symbols || []).filter((s) => (s.severity || classify(s.age_minutes).severity) !== "live").forEach((s) =>
    items.push(att(s.severity === "crit" ? "var(--aq-down)" : "var(--aq-amber)", `${s.symbol} on stale Lake data (${ageLabel(s.age_minutes)}) — excluded from decisions`)));
  if (data.pending_commands) items.push(att("var(--aq-blue)", data.pending_commands + " commands pending in the worker"));
  return items.length ? items.join("") : emptyState("No active alerts");
}

function att(color, text) {
  return `<div class="event"><span class="d" style="background:${color}"></span><span class="ty">${text}</span></div>`;
}

function buildFeed(fr) {
  const syms = fr.symbols || [];
  if (!syms.length) return emptyState("Freshness endpoint not available");
  return syms.map((s) => {
    const sev = s.severity || classify(s.age_minutes).severity;
    const stale = sev !== "live";
    const color = sev === "crit" ? "var(--aq-down)" : sev === "warn" ? "var(--aq-amber)" : "var(--aq-up)";
    const badgeCls = sev === "crit" ? "fresh-badge crit" : sev === "warn" ? "fresh-badge warn" : "fresh-badge";
    return `<div class="kv" style="opacity:${stale ? ".62" : "1"}">
      <span class="symcell"><span class="d" style="width:7px;height:7px;border-radius:50%;background:${color}"></span><span class="sym">${s.symbol}</span><span class="sym-name">${s.name || ""}</span></span>
      <span style="display:inline-flex;align-items:center;gap:6px"><span class="age" style="color:${stale ? color : "var(--aq-ink3)"}">${ageLabel(s.age_minutes)}</span><span class="${badgeCls}">${stale ? "STALE" : "LIVE"}</span></span>
    </div>`;
  }).join("");
}
