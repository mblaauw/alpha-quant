import store from "../state.js";
import { showBanner, clearBanner } from "../components/banner.js";
import { showModal, closeModal, intro, fieldStatic } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd, refreshView } from "../commands.js";
import { fmtDateTime } from "../formatters.js";
import { setFreshness, paintFeedPill } from "../freshness.js";

let eventSource = null;

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

  // Initial fetch, then switch to SSE
  await initialFetch();
  connectSSE();
}

function applyTheme() {
  document.documentElement.setAttribute("data-theme", store.theme);
  document.getElementById("theme-toggle").textContent = store.theme === "dark" ? "☀" : "☾";
}

function tickClock() {
  const s = new Date().toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  document.getElementById("header-time").textContent = s.toUpperCase() + " · LIVE";
}

async function initialFetch() {
  // One-shot fetch to paint the UI before SSE pushes its first event.
  try {
    const [ctx, fr] = await Promise.all([
      fetch("/v1/console/context").then(r => r.json()),
      fetch("/v1/console/freshness").then(r => r.json()),
    ]);
    store.context = ctx;
    store.bookId = ctx.active_book_id;
    store.freshness = fr;
    paintShell(ctx);
    paintFeedPill(fr);
    clearBanner();
  } catch (e) {
    showBanner("Initial load failed: " + e.message, "warning", "Offline");
  }
}

function applyContext(ctx) {
  const prevId = store.bookId;
  store.context = ctx;
  store.bookId = ctx.active_book_id;
  paintShell(ctx);
  clearBanner();
  // If book changed, dispatch a custom event so views can re-render.
  if (prevId && prevId !== ctx.active_book_id) {
    window.dispatchEvent(new CustomEvent("bookchange", { detail: { bookId: ctx.active_book_id } }));
  }
}

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/v1/console/stream");

  eventSource.addEventListener("context", (e) => {
    try { applyContext(JSON.parse(e.data)); } catch {}
  });

  eventSource.addEventListener("freshness", (e) => {
    try {
      const data = JSON.parse(e.data);
      setFreshness(data);
      paintFeedPill(data);
    } catch {}
  });

  eventSource.onerror = () => {
    // EventSource auto-reconnects; close and restart after a delay on hard failure.
    if (eventSource.readyState === EventSource.CLOSED) {
      setTimeout(connectSSE, 5000);
    }
  };
}

function paintShell(ctx) {
  const sel = document.getElementById("book-selector");
  if (ctx.books) {
    sel.innerHTML = ctx.books.map((b) => `<option value="${b.book_id}"${b.book_id === ctx.active_book_id ? " selected" : ""}>${b.label}</option>`).join("");
    sel.onchange = () => {
      store.bookId = sel.value;
      document.getElementById("book-label").textContent = "Book — " + (sel.options[sel.selectedIndex]?.text || "—");
      window.dispatchEvent(new CustomEvent("bookchange", { detail: { bookId: sel.value } }));
    };
    const active = ctx.books.find((b) => b.book_id === ctx.active_book_id);
    document.getElementById("book-label").textContent = "Book — " + (active ? active.label : "—");
  }
  document.getElementById("mode-badge").textContent = ctx.mode || "PAPER";
  const mockBadge = document.getElementById("mock-badge");
  if (ctx.mock_mode) {
    mockBadge.classList.remove("hidden");
  } else {
    mockBadge.classList.add("hidden");
  }
  document.getElementById("last-run-label").textContent = ctx.last_run ? "Last run " + fmtDateTime(ctx.last_run) : "No runs yet";
  const ops = document.getElementById("ops-status");
  ops.innerHTML = `<span class="d" style="background:${ctx.halted ? "var(--aq-down)" : "var(--aq-up)"}"></span>${ctx.halted ? "Halted" : "Ready"}`;
}

function openRunModal() {
  showModal(
    "Run decision cycle",
    intro("Evaluates the strategy policy against the latest knowable Lake facts. Stale symbols are excluded automatically.")
      + fieldStatic("Book", (store.context && store.context.books && store.context.books.find((b) => b.book_id === store.bookId)?.label) || "Active paper book")
      + fieldStatic("Decision as of", "Latest — live data"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "▶ Run", class: "btn btn-primary", onclick: () => { closeModal(); runWithToast(() => cmd.runCycle(store.bookId), "Decision cycle — latest", refreshView); } },
    ],
  );
}
