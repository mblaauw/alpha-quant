import store from "../state.js";
import { get } from "../api.js";
import { fmtDateTime, fmtNum, fmtCurrency } from "../formatters.js";
import { statusChip } from "../components/status.js";
import { emptyState } from "../components/empty_state.js";
import { errorState } from "../components/error_state.js";
import { renderTable } from "../components/table.js";
import { showModal, closeModal } from "../components/modal.js";
import { showBanner } from "../components/banner.js";
import { submitCommand, cancelCommand, generateKey } from "../commands.js";

export async function renderOrders() {
  const view = document.getElementById("view");
  view.innerHTML = `<div class="skeleton" style="height:200px"></div>`;
  try {
    const data = await get("/v1/console/orders");
    view.innerHTML = buildOrders(data);
    document.querySelectorAll("[data-cancel-order]").forEach(btn => {
      btn.addEventListener("click", () => confirmCancel(btn.dataset.cancelOrder));
    });
  } catch (e) {
    view.innerHTML = errorState("Failed to load orders", e.message);
  }
}

function buildOrders(data) {
  const rows = (data.items || []).map(o => [
    `<span class="mono">${o.order_id?.slice(0, 8)}</span>`,
    o.symbol,
    statusChip(o.side, o.side),
    fmtNum(o.requested_quantity),
    statusChip(o.status, o.status),
    fmtDateTime(o.created_at),
    o.status === "pending" ? `<button class="btn-ghost" data-cancel-order="${o.order_id}">Cancel</button>` : "",
  ]);
  return `
    <div class="section-header">Orders &amp; Fills</div>
    ${rows.length ? renderTable(["Order ID", "Symbol", "Side", "Qty", "Status", "Created", ""], rows) : emptyState("No orders")}
  `;
}

function confirmCancel(orderId) {
  showModal(
    "Cancel Pending Order",
    `<p>Are you sure you want to cancel order <strong>${orderId.slice(0, 8)}</strong>?</p>
     <div style="margin-top:0.75rem">
       <label class="metric-label">Reason (required)</label>
       <input id="cancel-reason" style="display:block;margin-top:4px;width:100%;font-family:var(--aq-font-ui);background:var(--aq-paper);color:var(--aq-ink);border:1px solid var(--aq-rule);border-radius:var(--aq-radius);padding:6px 8px" placeholder="Why is this order being cancelled?">
     </div>`,
    [
      { label: "Back", class: "btn", onclick: closeModal },
      { label: "✓ Cancel Order", class: "btn btn-danger", onclick: () => executeCancel(orderId) },
    ],
  );
}

async function executeCancel(orderId) {
  const reason = document.getElementById("cancel-reason")?.value;
  if (!reason) { showBanner("Cancellation reason is required.", "blocking"); return; }
  closeModal();
  showBanner("Submitting cancel command...", "info");
  try {
    const result = await cancelCommand(orderId);
    showBanner(`Cancel submitted: ${result.status}`, "info");
    await renderOrders();
  } catch (e) {
    showBanner("Cancel failed: " + e.message, "blocking");
  }
}
