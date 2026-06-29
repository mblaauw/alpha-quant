import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime, fmtCurrency, fmtNum, esc, chip } from "../formatters.js";
import { statusChip, tagChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { classify, ageLabel } from "../freshness.js";
import { showModal, closeModal, intro, fieldText, fieldSelect, fieldDateTime, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd, refreshView } from "../commands.js";
import { openRunDrawer } from "./drawers.js";

let _currentView = "overview";
let _runFilter = "all";
let _journalFilter = "all";

export async function renderSystem(view) {
  _currentView = view || "overview";
  const el = document.getElementById("view");
  el.innerHTML = `<div class="skeleton" style="height:320px"></div>`;

  try {
    const [sys, runs, journal] = await Promise.all([
      get("/v1/console/system"),
      get("/v1/console/runs"),
      get("/v1/console/journal"),
    ]);
    el.innerHTML = buildPage(sys, runs, journal);
    wireEvents();
  } catch (e) {
    el.innerHTML = errorState("Failed to load system data", e.message);
  }
}

function buildPage(sys, runsData, journalData) {
  const halted = sys.halted;
  const components = sys.components || {};
  const ctx = store.context || {};
  const fr = store.freshness || {};
  const feed = fr.symbols || [];

  switch (_currentView) {
    case "runs": return buildRunsView(runsData);
    case "journal": return buildJournalView(journalData);
    default: return buildOverview(halted, components, ctx, feed, runsData, journalData);
  }
}

/* ── OVERVIEW ─────────────────────────────────────────────── */

function buildOverview(halted, components, ctx, feed, runsData, journalData) {
  const comps = Object.entries(components);
  const liveN = feed.filter(s => {
    const sev = s.severity || classify(s.age_minutes).severity;
    return sev === "live";
  }).length;
  const staleN = feed.length - liveN;
  const postState = halted ? "halt" : (staleN > 0 ? "elevated" : "ready");
  const postIcon = halted ? "●" : (staleN > 0 ? "⚠" : "✓");
  const postText = halted
    ? "HALTED — all decision runs and paper execution are blocked"
    : staleN > 0
      ? `OPERATIONAL — ${staleN} Lake symbol${staleN > 1 ? "s" : ""} stale; decisions on those names fail closed`
      : "READY — all components healthy, every Lake symbol live";

  const headline = [
    { label: "System", value: halted ? "HALTED" : "READY", tone: halted ? "down" : "up", sub: halted ? "operations blocked" : "accepting runs" },
    { label: "Components", value: `${comps.filter(([,c]) => c.healthy).length} / ${comps.length}`, tone: "up", sub: "healthy" },
    { label: "Lake feed", value: `${liveN} · ${staleN}`, tone: staleN > 0 ? "warn" : "up", sub: `${liveN} live · ${staleN} stale` },
    { label: "Last run", value: ctx.last_run_status || "—", tone: ctx.last_run_status === "completed" ? "up" : ctx.last_run_status === "failed" ? "down" : "", sub: ctx.last_run_id ? fmtDateTime(ctx.last_run_as_of) : "no runs yet" },
    { label: "Active halts", value: halted ? "1" : "0", tone: halted ? "down" : "", sub: halted ? "operational halt" : "none" },
    { label: "Mode", value: ctx.mode || "PAPER", tone: "", sub: ctx.mock_mode ? "mock fixtures" : "live" },
  ];

  const compsHtml = comps.map(([k, v]) =>
    `<div class="kv"><span><span class="l">${esc(k)}</span>${v.detail ? `<span class="de">${esc(v.detail)}</span>` : ""}</span>${statusChip((v.status || "unknown").toUpperCase(), halted && k === "operational" ? "halted" : v.healthy ? "healthy" : "halted")}</div>`
  ).join("");

  const feedHtml = feed.map(s => {
    const sev = s.severity || classify(s.age_minutes).severity;
    const stale = sev !== "live";
    const color = sev === "crit" ? "var(--aq-down)" : sev === "warn" ? "var(--aq-amber)" : "var(--aq-up)";
    return `<div class="feedrow" style="opacity:${stale ? ".62" : "1"}">
      <span class="symcell"><span class="d" style="background:${color}"></span><span class="sym">${esc(s.symbol)}</span><span class="sym-name">${esc(s.name || "")}</span></span>
      <span class="rt"><span class="age" style="color:${stale ? color : "var(--aq-ink3)"}">${ageLabel(s.age_minutes)}</span><span class="fresh-badge" data-sev="${sev}">${stale ? "STALE" : "LIVE"}</span></span>
    </div>`;
  }).join("");

  const runs = (runsData.items || []).slice(0, 4);
  const recentRunsHtml = runs.length ? runs.map(r =>
    `<div class="sys-crow" data-run="${esc(r.run_id)}" style="grid-template-columns:1.1fr .9fr .8fr auto">
      <span class="rid">${esc(r.run_id.slice(0, 10))}</span>
      <span>${tagChip((r.run_kind || "").toUpperCase(), r.run_kind)}</span>
      <span>${statusChip((r.status || "").toUpperCase(), r.status)}</span>
      <span class="chev">›</span>
    </div>`
  ).join("") : emptyState("No runs");

  const journal = (journalData.items || []).slice(0, 4);
  const recentJournalHtml = journal.length ? journal.map(j =>
    `<div class="sys-crow" style="grid-template-columns:62px 1fr;cursor:default">
      <span class="age" style="font-size:10.5px">${j.timestamp ? fmtDateTime(j.timestamp) : ""}</span>
      <span class="tl-body"><span class="tl-dot" style="background:var(--aq-ink3);width:7px;height:7px"></span><span class="tl-msg" style="font-size:12px">${esc(j.message)}</span></span>
    </div>`
  ).join("") : emptyState("No journal entries");

  return `
    <div class="sys-posture" data-s="${postState}"><span class="pi">${postIcon}</span><span>${postText}</span></div>

    <div class="sys-metrics">
      ${headline.map(h => `<div class="sys-metric"><span class="sys-mlabel">${h.label}</span><span class="sys-mval" data-tone="${h.tone}">${h.value}</span><span class="sys-msub">${h.sub}</span></div>`).join("")}
    </div>

    <div class="grid-2">
      <div class="card" style="margin-bottom:0">
        <div class="card-head"><span class="card-cap">Components</span><span class="card-n">/v1/console/system</span></div>
        ${compsHtml || emptyState("No components")}
      </div>
      <div class="card" style="margin-bottom:0">
        <div class="card-head"><span class="card-cap">Runtime &amp; context</span><span class="card-n">/v1/console/context</span></div>
        <div class="kv"><span class="l">Active book</span><span class="r">${esc((ctx.books || []).find(b => b.book_id === ctx.active_book_id)?.label || ctx.active_book_id || "—")}</span></div>
        <div class="kv"><span class="l">Mode</span><span class="r">${esc(ctx.mode || "—")}</span></div>
        <div class="kv"><span class="l">Snapshot pin</span><span class="r" style="color:var(--aq-snap)">${ctx.snapshot || "—"}</span></div>
        <div class="kv"><span class="l">Last decision run</span><span class="r">${ctx.last_run_id ? esc(ctx.last_run_id.slice(0, 10) + " · " + ctx.last_run_status) : "—"}</span></div>
        <div class="kv">
          <span><span class="l">Mock mode</span><span class="de">${ctx.mock_mode ? "Serving canned fixtures" : "Live adapters"}</span></span>
          <span class="sys-toggle" id="mock-toggle" data-on="${ctx.mock_mode ? "true" : "false"}"><span class="tlabel">${ctx.mock_mode ? "ON" : "OFF"}</span><span class="tr"></span></span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><span class="card-cap">Lake feed · freshness gate</span><span class="card-n">/v1/console/freshness</span></div>
      ${feedHtml || emptyState("Freshness endpoint not available")}
    </div>

    <div class="grid-2">
      <div class="card" style="margin-bottom:0">
        <div class="sys-panel-head">
          <span class="sys-panel-title">Runs <span class="sub">${(runsData.items || []).length} total</span></span>
          <button class="sys-link" id="goto-runs">View all ${(runsData.items || []).length} ›</button>
        </div>
        ${recentRunsHtml}
      </div>
      <div class="card" style="margin-bottom:0">
        <div class="sys-panel-head">
          <span class="sys-panel-title">Journal <span class="sub">latest activity</span></span>
          <button class="sys-link" id="goto-journal">View all ›</button>
        </div>
        ${recentJournalHtml}
      </div>
    </div>`;
}

/* ── RUNS FULL VIEW ───────────────────────────────────────── */

function buildRunsView(runsData) {
  const allRuns = runsData.items || [];
  const filtered = _runFilter === "all" ? allRuns : allRuns.filter(r => (r.run_kind || "").toLowerCase() === _runFilter);
  const filters = ["all", "daily", "backtest", "replay"].map(t => ({
    label: t === "all" ? "All" : t.charAt(0).toUpperCase() + t.slice(1),
    val: t,
    on: _runFilter === t,
  }));

  const header = `<div class="dthead" style="grid-template-columns:1.2fr 1fr 1fr 1.1fr 1.1fr .4fr">
    <span>Run ID</span><span>Type</span><span>Status</span><span>Started</span><span>Completed</span><span></span></div>`;
  const rows = filtered.map(r =>
    `<div class="dtrow" data-run="${esc(r.run_id)}" style="grid-template-columns:1.2fr 1fr 1fr 1.1fr 1.1fr .4fr">
      <span class="rid">${esc(r.run_id.slice(0, 10))}</span>
      <span>${tagChip((r.run_kind || "").toUpperCase(), r.run_kind)}</span>
      <span>${tagChip((r.status || "").toUpperCase(), r.status)}</span>
      <span class="num" style="text-align:left;font-size:11px">${fmtDateTime(r.started_at)}</span>
      <span class="num" style="text-align:left;font-size:11px">${fmtDateTime(r.completed_at)}</span>
      <span class="chev">›</span>
    </div>`
  ).join("");

  return `
    <button class="sys-crumb" id="goto-overview">‹ System overview</button>
    <div class="sec-head">
      <div class="sec-title">Runs <span class="sub">decisions · backtests · replays</span></div>
      <button class="run-btn" id="bt-btn">+ Backtest / replay</button>
    </div>
    <div class="sys-filters">
      ${filters.map(f => `<button class="sys-fchip" data-on="${f.on ? "true" : "false"}" data-filter="${f.val}">${f.label}</button>`).join("")}
    </div>
    ${filtered.length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No runs match filter")}`;
}

/* ── JOURNAL FULL VIEW ─────────────────────────────────────── */

function buildJournalView(journalData) {
  const allItems = journalData.items || [];
  const cats = ["all", ...new Set(allItems.map(j => j.category || "other"))];
  const filtered = _journalFilter === "all" ? allItems : allItems.filter(j => j.category === _journalFilter);

  const entries = filtered.map(j =>
    `<div class="tl-item">
      <span class="tl-time"><span>${fmtDateTime(j.timestamp)}</span>${j.category ? `<span class="tl-cat">${esc(j.category)}</span>` : ""}</span>
      <span class="tl-body"><span class="tl-dot" style="background:var(--aq-ink3)"></span><span class="tl-msg">${esc(j.message)}</span></span>
    </div>`
  ).join("");

  return `
    <button class="sys-crumb" id="goto-overview">‹ System overview</button>
    <div class="sec-head">
      <div class="sec-title">Journal <span class="sub">immutable event timeline</span></div>
    </div>
    <div class="sys-filters">
      ${cats.map(c => `<button class="sys-fchip" data-on="${_journalFilter === c ? "true" : "false"}" data-filter="${c}">${c === "all" ? "All events" : esc(c)}</button>`).join("")}
    </div>
    <div class="card">
      <div class="timeline">${entries || emptyState("No journal entries")}</div>
    </div>`;
}

/* ── EVENT WIRING ──────────────────────────────────────────── */

function wireEvents() {
  document.getElementById("goto-overview")?.addEventListener("click", () => renderSystem("overview"));
  document.getElementById("goto-runs")?.addEventListener("click", () => renderSystem("runs"));
  document.getElementById("goto-journal")?.addEventListener("click", () => renderSystem("journal"));

  document.getElementById("bt-btn")?.addEventListener("click", openBacktestModal);

  document.querySelectorAll("[data-run]").forEach(el => {
    el.addEventListener("click", () => openRunDrawer(el.dataset.run));
  });

  document.querySelectorAll(".sys-fchip[data-filter]").forEach(el => {
    el.addEventListener("click", () => {
      const filter = el.dataset.filter;
      if (_currentView === "runs") {
        _runFilter = filter;
      } else if (_currentView === "journal") {
        _journalFilter = filter;
      }
      refreshView();
    });
  });

  document.getElementById("mock-toggle")?.addEventListener("click", () => {
    const next = !store.context?.mock_mode;
    fetch("/v1/console/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mock: next }),
    }).then(() => refreshView()).catch(() => {});
  });
}

function openBacktestModal() {
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
          runWithToast(() => cmd.backtest(store.bookId, payload, "Backtest from System"), payload.run_kind + " run", () => renderSystem("runs"));
        } },
    ]);
}
