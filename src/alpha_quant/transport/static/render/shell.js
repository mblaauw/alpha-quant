import store from "../state.js";
import { get } from "../api.js";
import { showBanner, clearBanner } from "../components/banner.js";
import { showModal, closeModal } from "../components/modal.js";
import { submitCommand, pollCommand, generateKey } from "../commands.js";
import { fmtDateTime } from "../formatters.js";

let contextPollInterval = null;

export async function initShell() {
  document.documentElement.setAttribute("data-theme", store.theme);
  document.getElementById("theme-toggle").textContent = store.theme === "dark" ? "☀" : "☾";

  document.getElementById("theme-toggle").addEventListener("click", () => {
    store.theme = store.theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", store.theme);
    document.getElementById("theme-toggle").textContent = store.theme === "dark" ? "☀" : "☾";
    localStorage.setItem("aq-theme", store.theme);
  });

  document.getElementById("run-btn").addEventListener("click", openRunModal);

  await refreshContext();
  contextPollInterval = setInterval(refreshContext, 15000);
}

async function refreshContext() {
  try {
    const ctx = await get("/v1/console/context");
    store.context = ctx;
    store.bookId = ctx.active_book_id;
    updateShell(ctx);
    clearBanner();
  } catch (e) {
    showBanner("Context load failed: " + e.message, "warning");
  }
}

function updateShell(ctx) {
  const sel = document.getElementById("book-selector");
  if (ctx.books) {
    sel.innerHTML = ctx.books.map(b => `<option value="${b.id}" ${b.id === ctx.active_book_id ? "selected" : ""}>${b.name}</option>`).join("");
    sel.onchange = () => { store.bookId = sel.value; };
  }
  document.getElementById("mode-badge").textContent = ctx.mode || "PAPER";
  document.getElementById("last-run-label").textContent = ctx.last_run ? `Last run: ${fmtDateTime(ctx.last_run)}` : "";
  document.getElementById("snapshot-label").textContent = ctx.snapshot ? `Snapshot: ${ctx.snapshot}` : "";
  document.getElementById("ops-status").innerHTML = `<span class="dot ${ctx.halted ? 'halted' : 'healthy'}"></span>${ctx.halted ? 'Halted' : 'Ready'}`;
  document.getElementById("lake-health").innerHTML = `<span class="dot ${ctx.lake_healthy ? 'healthy' : 'halted'}"></span>${ctx.lake_healthy ? 'Lake' : 'Lake down'}`;
}

function openRunModal() {
  const bookId = store.bookId || "";
  showModal(
    "Run Decision Cycle",
    `
      <div style="display:grid;gap:0.75rem">
        <div><label class="metric-label">Book</label><div style="margin-top:4px">${bookId || "Default paper book"}</div></div>
        <div><label class="metric-label">Decision as of</label>
          <input type="datetime-local" id="run-as-of" style="display:block;margin-top:4px;font-family:var(--aq-font-mono);background:var(--aq-paper);color:var(--aq-ink);border:1px solid var(--aq-rule);border-radius:var(--aq-radius);padding:6px 8px;width:100%">
        </div>
      </div>
    `,
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "▶ Run", class: "btn btn-primary", onclick: executeRun },
    ],
  );
}

async function executeRun() {
  closeModal();
  const asOf = document.getElementById("run-as-of")?.value;
  showBanner("Submitting decision run command...", "info");
  try {
    const result = await submitCommand("decision_run.create", {
      decision_as_of: asOf ? new Date(asOf).toISOString() : new Date().toISOString(),
      snapshot_id: null,
    }, { idempotency_key: generateKey(), book_id: store.bookId, reason: "Manual run from Desk" });
    showBanner(`Command submitted: ${result.command_id?.slice(0, 8)}... — ${result.status}`, "info");
    pollUntilDone(result.command_id);
  } catch (e) {
    showBanner("Failed to submit run command: " + e.message, "blocking");
  }
}

async function pollUntilDone(commandId) {
  const maxAttempts = 60;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000));
    try {
      const cmd = await pollCommand(commandId);
      if (cmd.status === "succeeded" || cmd.status === "completed") {
        showBanner(`Decision run ${cmd.command_id?.slice(0, 8)} completed.`, "info");
        await refreshContext();
        return;
      }
      if (cmd.status === "failed") {
        showBanner(`Run failed: ${cmd.failure_message || "Unknown error"}`, "blocking");
        return;
      }
      if (cmd.status === "cancelled") {
        showBanner("Run was cancelled.", "warning");
        return;
      }
    } catch {
      showBanner("Lost contact with command tracker.", "warning");
      return;
    }
  }
  showBanner("Run still in progress — check Runs tab.", "warning");
}
