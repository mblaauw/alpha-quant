import { apiPostCommand, apiPollCommand } from "./api.js";
import { getState } from "./state.js";
import { openModal, closeModal } from "./components/modal.js";

export function showCommandConfirm({ type, title, description, fields = [], danger = false, onSuccess }) {
  let html = `<h3>${title}</h3><p>${description}</p>`;
  if (fields.length) {
    html += fields.map(f => `
      <label>${f.label}</label>
      ${f.type === "textarea"
        ? `<textarea id="cmd-${f.name}" ${f.required ? "required" : ""}>${f.value || ""}</textarea>`
        : `<input id="cmd-${f.name}" type="${f.type || "text"}" value="${f.value || ""}" ${f.required ? "required" : ""}>`
      }
    `).join("");
  }
  html += `<div class="modal-actions">
    <button class="btn" onclick="window.__closeModal()">Cancel</button>
    <button class="btn ${danger ? "btn-danger" : "btn-primary"}" id="cmd-confirm-btn">${type}</button>
  </div>`;

  openModal(html);

  document.getElementById("cmd-confirm-btn").onclick = async () => {
    const payload = {};
    for (const f of fields) {
      const el = document.getElementById(`cmd-${f.name}`);
      if (el) payload[f.name] = el.value;
    }
    document.getElementById("cmd-confirm-btn").disabled = true;
    document.getElementById("cmd-confirm-btn").textContent = "Submitting...";

    try {
      const result = await apiPostCommand(type.split(".")[0] === type ? type : type, payload, {
        bookId: getState().bookId,
      });
      if (result.command_id) {
        apiPollCommand(result.command_id, 500, 30000).then(cmd => {
          if (onSuccess) onSuccess(cmd);
        });
      }
      closeModal();
    } catch (err) {
      document.getElementById("cmd-confirm-btn").disabled = false;
      document.getElementById("cmd-confirm-btn").textContent = title;
      alert(`Command failed: ${err.message}`);
    }
  };
}
