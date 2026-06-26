import { getState, setState } from "./state.js";
import { initRouter } from "./router.js";
import { apiGet } from "./api.js";
import { renderShell } from "./render/shell.js";
import { showCommandConfirm } from "./commands.js";

async function init() {
  setState({ theme: getState().theme });
  document.documentElement.setAttribute("data-theme", getState().theme);

  initRouter();
  renderShell();

  await refreshContext();
  setupEventListeners();
  startPolling();
}

async function refreshContext() {
  try {
    const ctx = await apiGet("/v1/dashboard/context");
    const asOfEl = document.getElementById("as-of-label");
    const snapshotEl = document.getElementById("snapshot-label");
    if (ctx.last_run_as_of) asOfEl.textContent = `as of ${ctx.last_run_as_of}`;
    if (ctx.last_run_id) snapshotEl.textContent = `snapshot ${ctx.last_run_id.slice(0, 8)}`;

    const opsBadge = document.getElementById("ops-badge");
    if (ctx.halted) {
      opsBadge.className = "badge badge-critical";
      opsBadge.textContent = "HALTED";
      showGlobalBanner(`System halted: ${ctx.halt_reason || "unknown reason"}`, "critical");
    } else {
      opsBadge.className = "badge badge-healthy";
      opsBadge.textContent = "Ops";
      hideGlobalBanner();
    }
  } catch (err) {
    const opsBadge = document.getElementById("ops-badge");
    opsBadge.className = "badge badge-critical";
    opsBadge.textContent = "ERR";
  }
}

async function checkLakeHealth() {
  try {
    const health = await apiGet("/livez");
    const badge = document.getElementById("lake-badge");
    badge.className = "badge badge-healthy";
    badge.textContent = "Lake ✓";
  } catch {
    const badge = document.getElementById("lake-badge");
    badge.className = "badge badge-critical";
    badge.textContent = "Lake ✗";
  }
}

function showGlobalBanner(msg, type) {
  const banner = document.getElementById("global-banner");
  banner.textContent = msg;
  banner.className = `active ${type}`;
}

function hideGlobalBanner() {
  const banner = document.getElementById("global-banner");
  banner.className = "";
  banner.textContent = "";
}

function setupEventListeners() {
  document.getElementById("theme-toggle").onclick = () => {
    const next = getState().theme === "dark" ? "light" : "dark";
    setState({ theme: next });
  };

  document.getElementById("run-btn").onclick = () => {
    showCommandConfirm({
      type: "decision_run.create",
      title: "Run Decision Cycle",
      description: "Execute a full decision pipeline using current Alpha-Lake state.",
      fields: [
        { name: "reason", label: "Reason", type: "text", required: false, value: "Manual run from dashboard" },
      ],
      danger: false,
    });
  };

  window.__closeModal = () => {
    import("./components/modal.js").then(m => m.closeModal());
  };
}

let healthInterval;
function startPolling() {
  refreshContext();
  checkLakeHealth();
  healthInterval = setInterval(() => {
    refreshContext();
    checkLakeHealth();
  }, 30000);
}

document.addEventListener("DOMContentLoaded", init);
