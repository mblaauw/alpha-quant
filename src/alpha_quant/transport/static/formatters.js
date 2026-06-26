export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtPct(v) { return v == null ? "—" : `${(v * 100).toFixed(1)}%`; }

export function fmtCurrency(v) {
  if (v == null) return "—";
  const a = Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
  return (v < 0 ? "-$" : "$") + a;
}

export function fmtPrice(v) {
  if (v == null) return "—";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtNum(v) { return v == null ? "—" : Number(v).toLocaleString("en-US"); }

/* Maps a status string to a chip tone class used by statusChip(). */
export function chip(state) {
  const s = String(state || "").toLowerCase();
  const ok = ["healthy", "ready", "completed", "succeeded", "filled", "reachable", "enter", "clear"];
  const warn = ["degraded", "attention", "partial", "running", "pending"];
  const bad = ["halted", "failed", "blocked", "critical", "cancelled", "rejected", "down", "stale"];
  const info = ["hold", "decision", "queued"];
  if (ok.includes(s)) return "chip ok";
  if (warn.includes(s)) return "chip warn";
  if (bad.includes(s)) return "chip bad";
  if (info.includes(s)) return "chip info";
  return "chip dim";
}
