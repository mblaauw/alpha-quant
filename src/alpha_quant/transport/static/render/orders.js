import store from "../state.js";
import { get } from "../api.js";
import { fmtNum, fmtTime, fmtDateTime } from "../formatters.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { tagChip } from "../components/status.js";
import { showModal, closeModal, intro, fieldText, fieldNumber, fieldSelect, val } from "../components/modal.js";
import { runWithToast } from "../components/toast.js";
import { cmd } from "../commands.js";
import { openOrderDrawer } from "./drawers.js";

const COLS = "1.3fr 1fr .8fr .7fr 1fr 1fr 1fr";

export async function renderOrders() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  try {
    const data = await get("/v1/console/orders");
    view.innerHTML = buildOrders(data);
    document.getElementById("new-order-btn").onclick = openNewOrder;
    document.querySelectorAll("[data-cancel]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); openCancel(b.dataset.cancel); });
    document.querySelectorAll("[data-order]").forEach((el) => { el.onclick = () => openOrderDrawer(el.dataset.order); });
  } catch (e) {
    view.innerHTML = errorState("Failed to load orders", e.message);
  }
}

function buildOrders(data) {
  const header = `<div class="dthead" style="grid-template-columns:${COLS}">
    <span>Order ID</span><span>Symbol</span><span>Side</span><span class="r-right">Qty</span><span>Status</span><span>Created</span><span class="r-right"></span></div>`;
  const rows = (data.items || []).map((o) => {
    const created = o.created_at ? fmtTime(o.created_at) : (o.created || "—");
    return `<div class="dtrow" style="grid-template-columns:${COLS}" data-order="${o.order_id}">
      <span class="age" style="font-size:11px">${(o.order_id || "").slice(0, 10) || "—"}</span>
      <span class="sym">${o.symbol}</span>
      <span>${tagChip((o.side || "").toUpperCase(), o.side === "buy" ? "enter" : "blocked")}</span>
      <span class="num">${fmtNum(o.requested_quantity ?? o.quantity)}</span>
      <span>${tagChip((o.status || "").toUpperCase(), o.status)}</span>
      <span class="age" style="font-size:11px">${created}</span>
      <span class="r-right">${o.status === "pending" ? `<button class="act-btn danger" data-cancel="${o.order_id}" data-stop-propagation>Cancel</button>` : ""}</span>
    </div>`;
  }).join("");

  return `
    <div class="sec-head"><div class="sec-title">Orders &amp; fills</div><button id="new-order-btn" class="run-btn">+ Manual order</button></div>
    ${(data.items || []).length ? `<div class="dtable">${header}${rows}</div>` : emptyState("No orders")}`;
}

function openNewOrder() {
  showModal("Manual order intent",
    intro("Submits a paper order intent. Rejected if the symbol's Lake data is stale.")
      + fieldSelect("o_sym", "Symbol", ["AAPL", "MSFT", "NVDA", "AMZN", "META", "JPM"])
      + fieldSelect("o_side", "Side", ["buy", "sell"])
      + fieldNumber("o_qty", "Quantity", 100)
      + fieldText("o_reason", "Reason", "Discretionary rationale"),
    [
      { label: "Cancel", class: "btn", onclick: closeModal },
      { label: "Submit order", class: "btn btn-primary", onclick: () => {
          const payload = { symbol: val("o_sym"), side: val("o_side"), quantity: parseInt(val("o_qty"), 10) || 100, order_type: "market" };
          closeModal();
          runWithToast(() => cmd.orderSubmit(store.bookId, payload, val("o_reason") || "Manual order"), `${payload.side} ${payload.quantity} ${payload.symbol}`, renderOrders);
        } },
    ]);
}

function openCancel(orderId) {
  showModal("Cancel order " + orderId.slice(0, 8),
    intro("Cancels this pending order. The paper engine will stop working it.")
      + fieldText("c_reason", "Reason (required)", "Why cancel?"),
    [
      { label: "Back", class: "btn", onclick: closeModal },
      { label: "✓ Cancel order", class: "btn btn-danger", onclick: () => {
          const reason = val("c_reason"); if (!reason) return;
          closeModal();
          runWithToast(() => cmd.orderCancel(store.bookId, orderId, reason), "Cancel " + orderId.slice(0, 8), renderOrders);
        } },
    ]);
}
