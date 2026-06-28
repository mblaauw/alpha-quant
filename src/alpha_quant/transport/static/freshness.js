import { get } from "./api.js";
import store from "./state.js";

/* Data-freshness model (see API plan §3). The Desk operates on latest data only;
   the single most important signal is how stale each symbol is. Severity:
     live  — within SLA
     warn  — beyond SLA (excluded from live decisions)
     crit  — far beyond SLA (> critical threshold) */

export function classify(ageMinutes, sla = 120, critical = 1440) {
  if (ageMinutes == null) return { severity: "live", stale: false };
  if (ageMinutes > critical) return { severity: "crit", stale: true };
  if (ageMinutes > sla) return { severity: "warn", stale: true };
  return { severity: "live", stale: false };
}

export function ageLabel(m) {
  if (m == null) return "—";
  if (m >= 1440) return Math.round(m / 1440) + "d ago";
  if (m >= 60) return Math.round(m / 60) + "h ago";
  return Math.round(m) + "m ago";
}

const BADGE = { live: "fresh-badge", warn: "fresh-badge warn", crit: "fresh-badge crit" };
const LABEL = { live: "LIVE", warn: "STALE", crit: "STALE" };

/* Inline badge for a symbol given its freshness block { age_minutes, severity }. */
export function freshBadge(f) {
  if (!f) return "";
  const sev = f.severity || classify(f.age_minutes).severity;
  return `<span class="${BADGE[sev]}">${LABEL[sev]}</span>`;
}

export function freshAge(f) {
  if (!f) return "";
  return `<span class="age">${ageLabel(f.age_minutes)}</span>`;
}

/* Look up cached freshness for a symbol. */
export function freshnessFor(symbol) {
  const fr = store.freshness;
  if (!fr || !fr.symbols) return null;
  return fr.symbols.find((s) => s.symbol === symbol) || null;
}

/* Accept freshness data pushed from the SSE stream. */
export function setFreshness(data) {
  store.freshness = data;
}

/* Fetch /v1/console/freshness, caching on the store. Tolerant: if the endpoint
   is not yet implemented, returns null and the UI falls back to per-item blocks.
   Used as fallback when SSE is unavailable. */
export async function loadFreshness() {
  try {
    const fr = await get("/v1/console/freshness");
    store.freshness = fr;
    return fr;
  } catch {
    store.freshness = null;
    return null;
  }
}

/* Updates the masthead Lake-feed pill from a freshness response. */
export function paintFeedPill(fr) {
  const pill = document.getElementById("feed-pill");
  const label = document.getElementById("feed-label");
  if (!pill || !label) return;
  if (!fr) { label.textContent = "Live"; pill.classList.remove("is-stale"); return; }
  const stale = fr.stale_count || 0;
  const fresh = fr.fresh_count != null ? fr.fresh_count : (fr.symbols ? fr.symbols.length - stale : 0);
  pill.classList.toggle("is-stale", stale > 0);
  label.textContent = stale > 0 ? `${fresh} fresh · ${stale} stale` : `All ${fresh} fresh`;
}
