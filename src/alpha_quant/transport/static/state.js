const state = {
  route: "command-center",
  bookId: null,
  books: [],
  mode: "PAPER",
  decisionAsOf: null,
  snapshotId: null,
  theme: localStorage.getItem("aq-theme") || "dark",
  sidebarCollapsed: JSON.parse(localStorage.getItem("aq-sidebar") || "false"),
  selectedRunId: null,
  selectedDecisionId: null,
  selectedCommandId: null,
  selectedPositionId: null,
  selectedOrderId: null,
  csrfToken: null,
};

export function getState() { return state; }

export function setState(updates) {
  Object.assign(state, updates);
  if (updates.theme !== undefined) {
    localStorage.setItem("aq-theme", state.theme);
    document.documentElement.setAttribute("data-theme", state.theme);
  }
  if (updates.sidebarCollapsed !== undefined) {
    localStorage.setItem("aq-sidebar", JSON.stringify(state.sidebarCollapsed));
  }
}

export function saveVisualPrefs() {
  localStorage.setItem("aq-theme", state.theme);
  localStorage.setItem("aq-sidebar", JSON.stringify(state.sidebarCollapsed));
  localStorage.setItem("aq-last-route", state.route);
}
