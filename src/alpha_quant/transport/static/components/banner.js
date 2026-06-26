/* Global banner. Tones: stale | blocking | warning | info. The `tag` is an
   optional uppercase kicker shown in the accent colour. */
export function showBanner(message, type = "info", tag = "") {
  const el = document.getElementById("global-banner");
  el.innerHTML = (tag ? `<span class="tag">${tag}</span>` : "") + `<span>${message}</span>`;
  el.className = `visible ${type}`;
}

export function clearBanner() {
  document.getElementById("global-banner").className = "";
}
