import store from "../state.js";
import { get } from "../api.js";
import { fmtCurrency, esc } from "../formatters.js";
import { errorState } from "../components/error_state.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";

function pct1(v) { return (v * 100).toFixed(1) + "%"; }
function pct0(v) { return (v * 100).toFixed(0) + "%"; }
function fmt(v, fn) { return v != null ? fn(v) : "—"; }

let _varMode = "p99";

function _pickLevel(varLevels) {
  return varLevels[_varMode] || varLevels.p99 || null;
}

export async function renderRisk() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/risk?book_id=" + (store.bookId || ""));
    view.innerHTML = buildRisk(data);
    wire(data);
  } catch (e) {
    view.innerHTML = errorState("Failed to load risk", e.message);
  }
}

window.addEventListener("bookchange", renderRisk);

// ── Gaussian tail histogram ──

function tailBars(z) {
  const N = 29;
  const bars = [];
  for (let i = 0; i < N; i++) {
    const x = -3.4 + i * (6.8 / (N - 1));
    bars.push({ h: Math.max(3, Math.round(Math.exp(-x * x / 2) * 100)) + "%", tail: x <= -z });
  }
  return bars;
}

// ── Build the full page ──

function buildRisk(data) {
  const headline = data.headline || {};
  const posture = data.posture || {};
  const postState = data.halted ? "halt" : (posture.state || "ready");
  const varData = data.var || {};
  const varLevels = varData.levels || {};
  const methodParams = varData.method_params || {};

  // Use active VaR mode (toggled by user)
  const varActive = _pickLevel(varLevels);
  const v99 = varLevels.p99 || null;
  const v95 = varLevels.p95 || null;
  const ves = varLevels.es975 || null;

  const varModeLabel = { p99: "99%", p95: "95%", es: "ES 97.5%" }[_varMode] || "99%";
  const varBudgetPct = { p99: 0.90, p95: 0.50, es: 0.60 }[_varMode] || 0.90;

  // Headline KPIs
  const hl = [
    { label: `1-day VaR ${varModeLabel}`, value: fmt(varActive ? varActive.pct : null, pct1), tone: "warn", sub: varActive ? `$${Math.round(varActive.usd).toLocaleString()} · ${pct0(headline.gross_cap || 0.90)} of budget` : "—" },
    { label: "Expected shortfall", value: fmt(headline.es_975_pct, pct1), tone: "", sub: fmt(headline.es_975_usd, v => "ES 97.5% · $" + Math.round(v).toLocaleString()) },
    { label: "Ann. volatility", value: fmt(headline.ann_vol, pct1), tone: "", sub: fmt(headline.ann_vol, v => "EWMA λ" + (methodParams.ewma_lambda || 0.94) + " · daily " + pct1(v / Math.sqrt(252))) },
    { label: "Portfolio beta", value: fmt(headline.beta, v => v.toFixed(2)), tone: "", sub: "to SPY · 105% net" },
    { label: "Current drawdown", value: fmt(headline.drawdown, pct1), tone: "", sub: fmt(headline.max_drawdown, v => "max " + pct1(v)) + " · limit " + fmt(headline.drawdown_limit, pct1) },
    { label: "Gross exposure", value: fmt(headline.gross_exposure, pct1), tone: "", sub: fmt(headline.gross_cap, v => "cap " + pct1(v)) },
    { label: "Effective bets", value: fmt(headline.effective_bets, v => v.toFixed(1)), tone: "warn", sub: (data.positions_count ? "of " + data.positions_count + " · " : "") + fmt(headline.hhi, v => "HHI " + v) },
  ];
  const headlineHTML = hl.map(h => `<div class="htile"><div class="hl">${esc(h.label)}</div><div class="hv" data-tone="${h.tone}">${esc(h.value)}</div><div class="hs">${esc(h.sub)}</div></div>`).join("");

  // Component VaR
  const compVar = (data.component_var || []).map(c => {
    const wCap = (c.weight || 0) * 100;
    const over = c.flagged;
    const width = Math.min(100, ((c.pct_of_var || 0) / 0.34) * 100);
    return `<div class="hbar">
      <div class="hbar-top">
        <span class="hbar-l"><span class="hbar-sym">${esc(c.symbol)}</span><span class="hbar-meta">σ ${c.vol ? pct0(c.vol) : "—"} · β ${(c.beta || 0).toFixed(2)} · wt ${wCap.toFixed(1)}%</span></span>
        <span class="hbar-v">${pct0(c.pct_of_var || 0)}</span>
      </div>
      <div class="hbar-track"><div class="hbar-fill" data-tone="${over ? "down" : "claret"}" style="width:${width}%"></div></div>
    </div>`;
  }).join("");

  // VaR tail histogram (default to 99%)
  const bars = tailBars(2.326);
  const tailHTML = bars.map(b => `<div class="tbar" data-tail="${b.tail}" style="height:${b.h}"></div>`).join("");

  // Scenarios
  const scenarios = (data.scenarios || []).map(s => {
    const maxLoss = Math.max(...(data.scenarios || []).map(x => Math.abs(x.pnl_pct || 0)), 0.01);
    const width = Math.min(100, Math.abs(s.pnl_pct || 0) / maxLoss * 100);
    const tone = s.kind === "hypothetical" ? "claret" : "down";
    return `<div class="rrow">
      <div class="rrow-top">
        <span class="rrow-l"><span class="rrow-name">${esc(s.name)}</span><span class="rrow-sub">${esc(s.kind === "historical" ? "Historical replay" : "Hypothetical shock")}</span></span>
        <span class="rrow-r"><span class="rrow-v">${esc(fmtCurrency(s.pnl_usd || 0))}</span><span class="rrow-vs">${esc(pct1(s.pnl_pct || 0))} equity</span></span>
      </div>
      <div class="rrow-track"><div class="rrow-fill" data-tone="${tone}" style="width:${width}%"></div></div>
    </div>`;
  }).join("");

  // Concentration
  const conc = data.concentration || {};
  const sectors = (conc.sectors || []).map(x => {
    const maxPct = Math.max(...(conc.sectors || []).map(s => s.pct || 0), 0.01);
    const width = Math.min(100, (x.pct || 0) / maxPct * 100);
    return `<div class="rrow">
      <div class="rrow-top">
        <span class="rrow-l"><span class="rrow-name">${esc(x.name)} ${x.breach ? '<span class="breach-chip">BREACH · CAP 70%</span>' : ""}</span><span class="rrow-sub">${esc(x.sub || "")}</span></span>
        <span class="rrow-r"><span class="rrow-v" data-tone="ink">${pct1(x.pct || 0)}</span></span>
      </div>
      <div class="rrow-track"><div class="rrow-fill" data-tone="${x.breach ? "down" : "up"}" style="width:${width}%"></div></div>
    </div>`;
  }).join("");

  // Factor exposures
  const factors = data.factors || {};
  const styles = (factors.styles || []).map(f => {
    const v = f.tilt || 0;
    const half = Math.abs(v) * 50;
    const neg = v < 0;
    return `<div class="frow">
      <span class="fname">${esc(f.name)}</span>
      <span class="ftrack"><span class="fcenter"></span><span class="ffill" data-neg="${neg}" style="left:${neg ? 50 - half : 50}%;width:${half}%"></span></span>
      <span class="fval">${v >= 0 ? "+" : ""}${v.toFixed(2)}</span>
    </div>`;
  }).join("");

  // Liquidity
  const liquidity = (data.liquidity || []).map(l => {
    const maxDays = Math.max(...(data.liquidity || []).map(x => x.days_to_liquidate || 0), 0.01);
    const width = Math.min(100, (l.days_to_liquidate || 0) / maxDays * 100);
    return `<div class="rrow">
      <div class="rrow-top">
        <span class="rrow-l"><span class="rrow-name">${esc(l.symbol)}</span><span class="rrow-sub">$${(l.adv_usd || 0).toExponential(1)} ADV · ${l.shares || 0} sh</span></span>
        <span class="rrow-r"><span class="rrow-v" data-tone="up">${(l.days_to_liquidate || 0).toFixed(2)}d</span></span>
      </div>
      <div class="rrow-track"><div class="rrow-fill" data-tone="up" style="width:${width}%"></div></div>
    </div>`;
  }).join("");

  // Limits
  const limits = (data.limits || []).map(m => {
    const util = m.utilization || 0;
    const width = Math.min(100, util * 100);
    const vtone = m.breach ? "down" : util > 0.85 ? "warn" : "up";
    const fillTone = m.breach ? "down" : util > 0.85 ? "warn" : "claret";
    return `<div class="rrow">
      <div class="rrow-top">
        <span class="rrow-l"><span class="rrow-name">${esc(m.name)} ${m.breach ? '<span class="breach-chip">BREACH</span>' : ""}</span><span class="rrow-sub">${esc(m.current)} · ${esc(m.limit)}</span></span>
        <span class="rrow-r"><span class="rrow-v" data-tone="${vtone}">${pct0(util)}</span><span class="rrow-vs">utilized</span></span>
      </div>
      <div class="rrow-track"><div class="rrow-fill" data-tone="${fillTone}" style="width:${width}%"></div></div>
    </div>`;
  }).join("");

  // Events
  const events = (data.events || []).map(e => {
    const color = e.severity === "crit" || e.severity === "critical" ? "var(--aq-down)" : e.severity === "warn" ? "var(--aq-amber)" : "var(--aq-blue)";
    return `<div class="evt"><span class="ed" style="background:${color}"></span><span class="evt-body"><span class="evt-ty">${esc(e.title || e.type || "")} <span class="evt-t">${esc(e.at || e.timestamp || "")}</span></span><span class="evt-de">${esc(e.detail || "")}</span></span></div>`;
  }).join("");

  // Halt button
  const haltLabel = data.halted ? "✓ Resume operations" : "● Create halt";
  const haltAct = data.halted ? "resume" : "halt";

  // Posture
  const postIcon = data.halted ? "●" : "⚠";
  const postLabel = data.halted ? "HALTED" : (postState === "ready" ? "READY" : "ELEVATED");

  return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap">
      <span class="post-badge" data-s="${postState}"><span class="d"></span>${postLabel}</span>
      <button class="halt-btn" data-act="${haltAct}" data-halt="${haltAct}">${haltLabel}</button>
    </div>
    <div class="posture" data-s="${postState}"><span class="pi">${postIcon}</span><span>${esc(posture.text || "Risk posture is within normal parameters.")}</span></div>
    <div class="hstrip">${headlineHTML}</div>
    <div class="rgrid">
      <!-- VaR & ES -->
      <div class="card">
        <div class="card-head"><span class="card-title">Value at Risk &amp; Expected Shortfall</span><span class="card-method">1-day · 3 models</span></div>
        <div class="var-top">
          <div class="var-big">${varActive ? pct1(varActive.pct) : "—"}<small>${varModeLabel} · 1d</small></div>
          <div class="seg">
            <button data-on="${_varMode === 'p99'}" data-var-mode="p99">99%</button>
            <button data-on="${_varMode === 'p95'}" data-var-mode="p95">95%</button>
            <button data-on="${_varMode === 'es'}" data-var-mode="es">ES 97.5%</button>
          </div>
        </div>
        <div class="var-note">1-day ${_varMode === 'es' ? 'expected shortfall' : 'VaR'}: loss above threshold in equity terms: <b style="color:var(--aq-down)">${varActive ? fmtCurrency(varActive.usd) : "—"}</b>.</div>
        <div class="tail">${tailHTML}</div>
        <div class="tail-x"><span>−3σ</span><span>loss ◂</span><span>0</span><span>▸ gain</span><span>+3σ</span></div>
        <div class="mcomp">
          <span class="mn">Parametric <b>variance–covariance</b> · EWMA λ${methodParams.ewma_lambda || "—"}</span><span class="mvv">${varActive ? esc(varActive.parametric) : "—"}</span>
          <span class="mn">Historical simulation <b>${methodParams.hist_window_days || "—"}-day</b></span><span class="mvv">${varActive ? esc(varActive.historical) : "—"}</span>
          <span class="mn">Monte Carlo <b>${methodParams.mc_paths ? (methodParams.mc_paths / 1000).toFixed(0) : "—"}k paths</b></span><span class="mvv">${varActive ? esc(varActive.monte_carlo) : "—"}</span>
        </div>
      </div>
      <!-- Component VaR -->
      <div class="card">
        <div class="card-head"><span class="card-title">Risk contribution</span><span class="card-method">Component VaR · Euler</span></div>
        <div class="var-note" style="margin-top:0">Share of 1-day 99% VaR by position (marginal × weight). A name above its capital weight is carrying disproportionate risk.</div>
        ${compVar || '<div class="card-note">No positions to compute component VaR.</div>'}
      </div>
      <!-- Stress & scenario analysis -->
      <div class="card span2">
        <div class="card-head"><span class="card-title">Stress &amp; scenario analysis</span><span class="card-method">Historical replay + factor shocks</span></div>
        <div class="card-note">Full-revaluation P&amp;L if each scenario repeated against today's book. <b>Ranked by severity.</b></div>
        <div class="two-col">${scenarios || '<div class="card-note">No scenario data available.</div>'}</div>
      </div>
      <!-- Concentration -->
      <div class="card">
        <div class="card-head"><span class="card-title">Concentration &amp; diversification</span><span class="card-method">HHI · effective N</span></div>
        <div class="conc-grid">
          <div class="conc-stat"><div class="cl">Effective bets</div><div class="cv" data-tone="warn">${fmt(conc.effective_bets, v => v.toFixed(1))}</div><div class="cs">of ${data.positions_count || "—"} names · 1/HHI</div></div>
          <div class="conc-stat"><div class="cl">Herfindahl HHI</div><div class="cv" data-tone="warn">${fmt(conc.hhi, v => Math.round(v))}</div><div class="cs">concentrated &gt;1,800</div></div>
          <div class="conc-stat"><div class="cl">Avg correlation</div><div class="cv" data-tone="warn">${fmt(conc.avg_correlation, v => v.toFixed(2))}</div><div class="cs">20d</div></div>
        </div>
        <div class="card-note" style="margin-bottom:11px"><b>Sector weights</b> · diversification ratio ${fmt(conc.diversification_ratio, v => v.toFixed(2))} · top-3 names ${fmt(conc.top3_pct, pct0)} of gross</div>
        ${sectors}
      </div>
      <!-- Factor exposures -->
      <div class="card">
        <div class="card-head"><span class="card-title">Factor exposures</span><span class="card-method">Barra-style · net tilt</span></div>
        <div class="fbeta"><span class="l">Market beta (to SPY)</span><span class="v">${fmt(factors.beta, v => v.toFixed(2))}</span></div>
        <div class="card-note" style="margin-top:0;margin-bottom:13px">Standardized style tilts, −1 to +1.</div>
        ${styles}
      </div>
      <!-- Liquidity -->
      <div class="card">
        <div class="card-head"><span class="card-title">Liquidity horizon</span><span class="card-method">Days to liquidate · 20% ADV</span></div>
        <div class="card-note" style="margin-top:0">Sessions to exit each position at 20% of average daily volume.</div>
        ${liquidity || '<div class="card-note">No liquidity data.</div>'}
      </div>
      <!-- Limits -->
      <div class="card">
        <div class="card-head"><span class="card-title">Limits &amp; circuit breakers</span><span class="card-method">Utilization vs policy</span></div>
        <div class="card-note" style="margin-top:0">Each limit as % of its cap.</div>
        ${limits || '<div class="card-note">No limit data configured.</div>'}
      </div>
      <!-- Risk events -->
      <div class="card span2">
        <div class="card-head"><span class="card-title">Risk events &amp; alerts</span></div>
        ${events || '<div class="card-note">No recent risk events.</div>'}
      </div>
    </div>`;
}

// ── Wire events and halt/resume ──

function wire(data) {
  // Halt/resume button
  document.querySelector("[data-halt]")?.addEventListener("click", () => openConfirm(data.halted));

  // VaR mode toggle — switch active percentile and re-render
  document.querySelectorAll("[data-var-mode]").forEach(b => {
    b.addEventListener("click", () => {
      _varMode = b.dataset.varMode;
      renderRisk();
    });
  });
}

function openConfirm(halted) {
  // Build a confirm modal dynamically
  const overlay = document.getElementById("confirm-overlay");
  if (overlay) overlay.remove();

  const div = document.createElement("div");
  div.id = "confirm-overlay";
  div.className = "tk-overlay";
  div.dataset.open = "true";
  div.innerHTML = `<div class="confirm">
    <h3>${halted ? "Resume operations" : "Create operational halt"}</h3>
    <p>${halted ? "Clears the active halt and re-enables decision runs and paper execution." : "Blocks all decision runs and paper execution across this book until the halt is cleared."}</p>
    <input id="confirm-reason" placeholder="Reason (recorded with the command)" value="">
    <div class="confirm-acts">
      <button class="btn" id="confirm-cancel">Cancel</button>
      <button class="btn" data-variant="${halted ? "go" : "danger"}" id="confirm-go">${halted ? "✓ Resume" : "● Create halt"}</button>
    </div>
  </div>`;
  document.body.appendChild(div);

  document.getElementById("confirm-cancel").onclick = () => div.remove();
  document.getElementById("confirm-overlay").onclick = (e) => { if (e.target === e.currentTarget) div.remove(); };
  document.getElementById("confirm-go").onclick = () => {
    const reason = document.getElementById("confirm-reason").value || "No reason given";
    div.remove();
    if (halted) {
      runWithToast(() => cmd.haltResume(store.bookId, reason), "Resume operations", renderRisk);
    } else {
      runWithToast(() => cmd.haltCreate(store.bookId, reason), "Create halt", renderRisk);
    }
  };
}
