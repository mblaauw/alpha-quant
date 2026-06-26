import { apiGet } from "../api.js";
import { openDrawer } from "../components/drawer.js";
import { loading } from "../components/empty_state.js";

export async function renderReports(container) {
  container.innerHTML = loading("Loading reports...");
  try {
    const data = await apiGet("/v1/dashboard/reports");
    const items = data.items || [];

    if (items.length === 0) {
      container.innerHTML = `<div class="empty-state"><h3>No reports yet</h3><p>Generated reports will appear here.</p></div>`;
      return;
    }

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Reports</h2>
      <div class="card">
        <table class="data-table">
          <thead><tr><th>Date</th><th>Type</th><th></th></tr></thead>
          <tbody>
            ${items.map(r => `
              <tr class="clickable" onclick="window.__openReport('${r.report_date}', '${r.report_type}')">
                <td>${r.report_date || "-"}</td>
                <td>${r.report_type || "-"}</td>
                <td>View →</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;

    window.__openReport = async (date, type) => {
      try {
        const content = await apiGet(`/v1/dashboard/reports/${date}/${type}`);
        const body = typeof content === "string" ? content : content?.content || JSON.stringify(content);
        openDrawer(`Report: ${type} ${date}`, `<pre style="white-space:pre-wrap;font-size:0.85rem">${body}</pre>`);
      } catch (err) {
        alert("Failed: " + err.message);
      }
    };

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load reports</h3><p>${err.message}</p></div>`;
  }
}
