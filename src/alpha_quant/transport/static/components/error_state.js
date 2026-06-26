export function errorState(title, detail) {
  return `<div class="error-state"><div class="error-state-title">${title}</div>${detail ? `<div class="error-state-detail">${detail}</div>` : ""}</div>`;
}
