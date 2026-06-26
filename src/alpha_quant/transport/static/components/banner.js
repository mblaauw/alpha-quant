export function showBanner(message, type = "info") {
  const el = document.getElementById("global-banner");
  el.textContent = message;
  el.className = `visible ${type}`;
}

export function clearBanner() {
  document.getElementById("global-banner").className = "";
}
