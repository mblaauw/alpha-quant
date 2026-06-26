import { apiGet } from "../api.js";
import { loading } from "../components/empty_state.js";

export async function renderJournal(container) {
  container.innerHTML = loading("Loading journal...");
  try {
    const data = await apiGet("/v1/dashboard/journal");
    const items = data.items || [];

    if (items.length === 0) {
      container.innerHTML = `<div class="empty-state"><h3>Journal is empty</h3><p>Journal entries will appear as the system operates.</p></div>`;
      return;
    }

    container.innerHTML = `
      <h2 style="margin-bottom:16px">Journal</h2>
      <div class="card">
        ${items.map(e => `
          <div style="padding:12px 16px;border-bottom:1px solid var(--aq-border)">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
              <span class="status-dot ${e.event_type?.includes("risk") || e.event_type?.includes("halt") ? "critical" : "healthy"}"></span>
              <span style="font-weight:600;font-size:0.85rem">${e.event_type || e.type || "event"}</span>
              <span style="color:var(--aq-ink-muted);font-size:0.8rem">${e.created_at || e.timestamp || "-"}</span>
            </div>
            <div style="font-size:0.85rem;color:var(--aq-ink-muted)">${e.payload || e.description || e.reason || JSON.stringify(e)}</div>
          </div>
        `).join("")}
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div class="error-state"><h3>Failed to load journal</h3><p>${err.message}</p></div>`;
  }
}
