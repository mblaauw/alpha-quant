export function emptyState(message = "No data available.") {
  return `<div class="empty-state"><div class="empty-state-icon">◌</div><div class="empty-state-text">${message}</div></div>`;
}
