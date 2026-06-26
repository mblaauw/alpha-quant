export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtPct(v) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtCurrency(v) {
  if (v == null) return "—";
  const abs = Math.abs(v).toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return v < 0 ? `-${abs}` : abs;
}

export function fmtNum(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString();
}

export function chip(status) {
  const map = {
    healthy: "chip healthy", completed: "chip completed", succeeded: "chip succeeded",
    failed: "chip failed", halted: "chip halted", running: "chip running", pending: "chip pending",
    degraded: "chip warning", blocked: "chip blocked", ready: "chip ready",
  };
  return map[status] || "chip neutral";
}
