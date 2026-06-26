import { pollCommand } from "../commands.js";

/* Command toast: shows the queued → running → succeeded/failed lifecycle of a
   submitted command in the bottom-right, mirroring the operational-command model.

   runWithToast(submitFn, label, onSucceed):
     submitFn  — () => Promise<{ command_id, status }>
     label     — human label for the toast
     onSucceed — optional () => void, called on success (e.g. re-render) */

const el = () => document.getElementById("toast");

function paint(status, label, id, detail) {
  const t = el();
  t.className = "show " + status.toLowerCase();
  document.getElementById("toast-status-label").textContent = status.toUpperCase();
  document.getElementById("toast-label").textContent = label;
  document.getElementById("toast-id").textContent = id ? id.slice(0, 12) : "";
  document.getElementById("toast-detail").textContent = detail || "";
}

function hideLater(ms = 4200) {
  setTimeout(() => { el().className = ""; }, ms);
}

export async function runWithToast(submitFn, label, onSucceed) {
  paint("queued", label, "", "Submitting command…");
  let res;
  try {
    res = await submitFn();
  } catch (e) {
    paint("failed", label, "", "Submit failed: " + e.message);
    hideLater();
    return;
  }
  const id = res.command_id;
  paint(res.status === "running" ? "running" : "queued", label, id, "Accepted — awaiting worker");

  // Poll the command until terminal.
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    let cmd;
    try { cmd = await pollCommand(id); } catch { paint("failed", label, id, "Lost contact with command tracker"); hideLater(); return; }
    const s = cmd.status;
    if (s === "running") paint("running", label, id, "Worker executing…");
    if (s === "succeeded" || s === "completed") {
      paint("succeeded", label, id, "Committed · " + id.slice(0, 8));
      if (onSucceed) onSucceed();
      hideLater();
      return;
    }
    if (s === "failed") {
      const msg = cmd.failure_code === "STALE_DATA"
        ? "Rejected — stale Lake data: " + (cmd.failure_message || "")
        : (cmd.failure_message || "Command failed");
      paint("failed", label, id, msg);
      hideLater(6000);
      return;
    }
    if (s === "cancelled") { paint("failed", label, id, "Cancelled"); hideLater(); return; }
  }
  paint("running", label, id, "Still running — see Runs tab");
  hideLater();
}
