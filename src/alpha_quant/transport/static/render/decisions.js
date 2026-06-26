import { apiGet } from "../api.js";
import { openDrawer, closeDrawer } from "../components/drawer.js";
import { loading } from "../components/empty_state.js";

export async function renderDecisions(container) {
  container.innerHTML = loading("Loading decisions...");
  try {
    const data = await apiGet("/v1/dashboard/decisions");
    const items = data.items || [];

    if (items.length === 0) {
      container.innerHTML = `<div class="empty-state"><h3>No decisions yet</h3><p>Decision records will appear after a pipeline run.</p></div>`;
      return;
    }

    let rows = items.map(d => `
      <tr class="clickable" onclick="window.__openDecision('${d.candidate_id || d.symbol}')">
        <td>${d.symbol || "-"}</td>
        <td>${d.action || d.decision || "-"}</td>
        <td>${d.score !== undefined ? d.score.toFixed(2) : "-"}</td>
        <td>${d.reason || d.reasons || "-"}</td>
        <td>${d.run_id ? d.run_id.slice(0, 8) + "..." : "-"}</td>
      </tr>
    `).join("");

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Decisions</h2>
      <div class="card">
        <table class="data-table">
          <thead><tr>
            <th>Symbol</th><th>Decision</th><th>Score</th><th>Reason</th><th>Run</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;

    window.__openDecision = async (id) => {
      try {
        const detail = await apiGet(`/v1/dashboard/decisions/${encodeURIComponent(id)}`);
        openDrawer("Decision Evidence", `
          <div class="kv-list">
            ${Object.entries(detail.decision || detail).map(([k, v]) =>
              `<div class="kv-item"><span class="kv-key">${k}</span><span class="kv-value">${typeof v === "object" ? JSON.stringify(v) : v}</span></div>`
            ).join("")}
          </div>
        `);
      } catch (err) {
        alert("Failed to load decision: " + err.message);
      }
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load decisions</h3><p>${err.message}</p></div>`;
  }
}
