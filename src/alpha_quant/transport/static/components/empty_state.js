export function loading(msg = "Loading...") {
  return `<div class="loading-state"><p>${msg}</p></div>`;
}

export function empty({ title = "Nothing here", message = "" } = {}) {
  return `<div class="empty-state"><h3>${title}</h3>${message ? `<p>${message}</p>` : ""}</div>`;
}

export function error(message) {
  return `<div class="error-state"><p>${message}</p></div>`;
}
