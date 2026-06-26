import { apiGet } from "../api.js";
import { showCommandConfirm } from "../commands.js";
import { loading } from "../components/empty_state.js";

export async function renderOrders(container) {
  container.innerHTML = loading("Loading orders...");
  try {
    const ordersData = await apiGet("/v1/dashboard/orders");
    const fillsData = await apiGet("/v1/dashboard/fills");
    const orders = ordersData.items || [];
    const fills = fillsData.items || [];

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Orders &amp; Fills</h2>

      <div class="tabs">
        <button class="tab active" data-tab="orders">Orders (${orders.length})</button>
        <button class="tab" data-tab="fills">Fills (${fills.length})</button>
      </div>

      <div id="orders-tab" class="tab-content">
        <div class="card">
          ${orders.length ? `
            <table class="data-table">
              <thead><tr>
                <th>Order ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Created</th><th></th>
              </tr></thead>
              <tbody>
                ${orders.map(o => `
                  <tr>
                    <td>${(o.order_id || "").slice(0, 8)}</td>
                    <td>${o.symbol || "-"}</td>
                    <td>${o.side || "-"}</td>
                    <td>${o.quantity || 0}</td>
                    <td>${o.status || "-"}</td>
                    <td>${o.created_at ? new Date(o.created_at).toLocaleDateString() : "-"}</td>
                    <td>${o.status === "pending" ? `<button class="btn btn-danger" onclick="window.__cancelOrder('${o.order_id}')">Cancel</button>` : ""}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          ` : `<div class="empty-state"><p>No orders</p></div>`}
        </div>
      </div>

      <div id="fills-tab" class="tab-content" style="display:none">
        <div class="card">
          ${fills.length ? `
            <table class="data-table">
              <thead><tr>
                <th>Fill ID</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Timestamp</th>
              </tr></thead>
              <tbody>
                ${fills.map(f => `
                  <tr>
                    <td>${(f.fill_id || "").slice(0, 8)}</td>
                    <td>${f.symbol || "-"}</td>
                    <td>${f.quantity || 0}</td>
                    <td>$${(f.price || 0).toFixed(2)}</td>
                    <td>${f.created_at ? new Date(f.created_at).toLocaleString() : "-"}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          ` : `<div class="empty-state"><p>No fills</p></div>`}
        </div>
      </div>
    `;

    document.querySelectorAll(".tab").forEach(tab => {
      tab.onclick = () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(tc => tc.style.display = "none");
        tab.classList.add("active");
        const target = document.getElementById(`${tab.dataset.tab}-tab`);
        if (target) target.style.display = "block";
      };
    });

    window.__cancelOrder = (orderId) => {
      showCommandConfirm({
        type: "paper_order.cancel",
        title: "Cancel Order",
        description: `Cancel pending order ${orderId.slice(0, 8)}?`,
        fields: [{ name: "reason", label: "Reason", type: "text", required: true }],
        danger: true,
        onSuccess: () => renderOrders(container),
      });
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load orders</h3><p>${err.message}</p></div>`;
  }
}
