import store from "../state.js";
import { get } from "../api.js";
import { showBanner, clearBanner } from "../components/banner.js";
import { showModal, closeModal, intro, fieldStatic } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import { fmtDateTime } from "../formatters.js";
import { loadFreshness, paintFeedPill } from "../freshness.js";
import "../components/tooltip.js";

let pollTimer = null;

export async function initShell() {
  store.theme = localStorage.getItem("aq-theme") || "light";
  applyTheme();

  document.getElementById("theme-toggle").addEventListener("click", () => {
    store.theme = store.theme === "dark" ? "light" : "dark";
    localStorage.setItem("aq-theme", store.theme);
    applyTheme();
  });

  document.getElementById("run-btn").addEventListener("click", openRunModal);
  tickClock();
  setInterval(tickClock, 30000);

  await Promise.all([refreshContext(), refreshFreshness()]);
  pollTimer = setInterval(() => { refreshContext(); refreshFreshness(); }, 15000);
}

function applyTheme() {
  document.documentElement.setAttribute("data-theme", store.theme);
  document.getElementById("theme-toggle").textContent = store.theme === "dark" ? "☀" : "☾";
}

function tickClock() {
  const s = new Date().toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  document.getElementById("header-time").textContent = s.toUpperCase() + " · LIVE";
}

async function refreshContext() {
  try {
    const ctx = await get("/v1/console/context");
    store.context = ctx;
    store.bookId = ctx.active_book_id;
    paintShell(ctx);
    clearBanner();
  } catch (e) {
    showBanner("Context load failed: " + e.message, "warning", "Offline");
  }
}

async function refreshFreshness() {
  const fr = await loadFreshness();
  paintFeedPill(fr);
}

function paintShell(ctx) {
  const sel = document.getElementById("book-selector");
  if (ctx.books) {
    sel.innerHTML = ctx.books.map((b) => `<option value="${b.id}"${b.id === ctx.active_book_id ? " selected" : ""}>${b.name}</option>`).join("");
    sel.onchange = () => { store.bookId = sel.value; };
    const active = ctx.books.find((b) => b.id === ctx.active_book_id);
    document.getElementById("book-label").textContent = "Book — " + (active ? active.name : "—");
  }
  document.getElementById("mode-badge").textContent = ctx.mode || "PAPER";
  document.getElementById("last-run-label").textContent = ctx.last_run ? "Last run " + fmtDateTime(ctx.last_run) : "No runs yet";
  const ops = document.getElementById("ops-status");
  ops.innerHTML = `<span class="d" style="background:${ctx.halted ? "var(--aq-down)" : "var(--aq-up)"}"></span>${ctx.halted ? "Halted" : "Ready"}`;
}

function openRunModal() {
  showModal(
    "Run decision cycle",
    intro("Evaluates the strategy policy against the latest knowable Lake facts. Stale symbols are excluded automatically.")
      + fieldStatic("Book", (store.context && store.context.active_book_name) || "Active paper book")
      + fieldStatic("Decision as of", "Latest — live data"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "▶ Run", class: "btn btn-primary", onclick: () => { closeModal(); runWithToast(() => cmd.runCycle(store.bookId), "Decision cycle — latest", refreshContext); } },
    ],
  );
}
